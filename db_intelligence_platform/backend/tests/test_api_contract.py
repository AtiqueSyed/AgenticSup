"""The frozen HTTP contract: route table, parameter names, and response envelopes.

`tests/fixtures/openapi_baseline.json` is a snapshot of the old `app/api/endpoints.py`
router. If this file ever needs to change, that is a deliberate, reviewed break of the
frontend contract -- not something a refactor should do by accident.
"""

import json
from pathlib import Path

from unittest.mock import AsyncMock

import pytest

BASELINE_PATH = Path(__file__).parent / "fixtures" / "openapi_baseline.json"


def _route_table(openapi: dict) -> dict[tuple[str, str], list[str]]:
    """{(METHOD, path): sorted parameter names} for every operation in the schema."""
    table: dict[tuple[str, str], list[str]] = {}
    for path, methods in openapi["paths"].items():
        for method, info in methods.items():
            params = sorted(p["name"] for p in info.get("parameters", []))
            table[(method.upper(), path)] = params
    return table


@pytest.fixture(scope="module")
def baseline_table() -> dict[tuple[str, str], list[str]]:
    return _route_table(json.loads(BASELINE_PATH.read_text()))


def test_route_table_matches_baseline(app, baseline_table):
    actual = _route_table(app.openapi())
    assert set(actual) == set(baseline_table), (
        f"Routes changed.\nMissing: {set(baseline_table) - set(actual)}\n"
        f"Added: {set(actual) - set(baseline_table)}"
    )


def test_parameter_names_match_baseline(app, baseline_table):
    actual = _route_table(app.openapi())
    for key, expected_params in baseline_table.items():
        assert actual[key] == expected_params, f"{key} parameter names changed"


def test_expected_path_parameters_present(app):
    """Spot-check the specific path/query parameter names the frontend depends on."""
    actual = _route_table(app.openapi())
    assert actual[("GET", "/api/v1/graph")] == ["database_id"]
    assert actual[("DELETE", "/api/v1/onboard/{database_id}")] == ["database_id"]
    assert actual[("GET", "/api/v1/onboard/{database_id}/status")] == ["database_id"]
    assert actual[("DELETE", "/api/v1/graph/node/{node_id}")] == ["node_id"]
    assert actual[("DELETE", "/api/v1/graph/edge/{source_id}/{target_id}/{edge_type}")] == [
        "edge_type",
        "source_id",
        "target_id",
    ]


# --------------------------------------------------------------------- reachability


async def test_health(async_client):
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    assert set(resp.json().keys()) == {"status", "llm_provider", "oracle_host", "neo4j_uri"}


async def test_stats(async_client):
    resp = await async_client.get("/api/v1/stats")
    assert resp.status_code == 200
    assert set(resp.json().keys()) == {
        "total_databases",
        "database_names",
        "databases",
        "entities_identified",
        "queries_today",
    }


async def test_graph_read(async_client):
    resp = await async_client.get("/api/v1/graph")
    assert resp.status_code == 200
    assert set(resp.json().keys()) == {"nodes", "edges"}


async def test_graph_read_scoped_by_database_id(async_client):
    resp = await async_client.get("/api/v1/graph", params={"database_id": "some-db"})
    assert resp.status_code == 200
    assert set(resp.json().keys()) == {"nodes", "edges"}


async def test_onboard(async_client):
    resp = await async_client.post(
        "/api/v1/onboard",
        json={
            "database_name": "Test DB",
            "connection_string": "oracle+oracledb_async://user:pass@host:1521/?service_name=x",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "Onboarding started"
    assert "database_id" in body and body["database_id"]


async def test_query_response_always_has_all_six_keys(async_client):
    resp = await async_client.post("/api/v1/query", json={"question": "How many users are there?"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {
        "database_id",
        "database_name",
        "answer",
        "sql_used",
        "visualizations",
        "results",
    }
    # The mocked LLM can't produce a real answer, but the key must still be present.
    assert isinstance(body["answer"], str)


# ------------------------------------------------------------- graph mutation shapes


async def test_delete_edge_response_has_no_null_extra_keys(async_client):
    resp = await async_client.delete("/api/v1/graph/edge/a/b/RELATES_TO")
    assert resp.status_code == 200
    assert resp.json() == {"status": "deleted"}


async def test_create_node_response_has_no_null_extra_keys(async_client):
    resp = await async_client.post(
        "/api/v1/graph/node",
        json={"id": "n1", "name": "Node One", "type": "Entity", "description": ""},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "created", "node_id": "n1"}


async def test_create_edge_response_excludes_null_node_id(async_client):
    resp = await async_client.post(
        "/api/v1/graph/edge", json={"source": "a", "target": "b", "type": "RELATES_TO"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "created", "source": "a", "target": "b"}


async def test_create_edge_404s_when_an_endpoint_is_missing(clients, async_client):
    """Both endpoints are MATCHed, so an unknown id writes nothing. The route must say
    so rather than returning the "created" it used to return unconditionally."""
    clients.neo4j.run = AsyncMock(return_value=[])
    resp = await async_client.post(
        "/api/v1/graph/edge", json={"source": "ghost", "target": "b", "type": "RELATES_TO"}
    )
    assert resp.status_code == 404


async def test_delete_node_response_has_no_null_extra_keys(async_client):
    resp = await async_client.delete("/api/v1/graph/node/n1")
    assert resp.status_code == 200
    assert resp.json() == {"status": "deleted", "node_id": "n1"}


# -------------------------------------------------------- degraded mode: no Neo4j


async def test_graph_mutations_500_without_neo4j(client_factory, clients_no_neo4j):
    async with client_factory(clients_no_neo4j) as client:
        create_node = await client.post(
            "/api/v1/graph/node",
            json={"id": "n1", "name": "Node One", "type": "Entity", "description": ""},
        )
        create_edge = await client.post(
            "/api/v1/graph/edge", json={"source": "a", "target": "b", "type": "RELATES_TO"}
        )
        delete_node = await client.delete("/api/v1/graph/node/n1")
        delete_edge = await client.delete("/api/v1/graph/edge/a/b/RELATES_TO")

    for resp in (create_node, create_edge, delete_node, delete_edge):
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Neo4j not connected"

"""Shared fixtures for the backend test suite.

There is no live Oracle, Neo4j, Elasticsearch, or Hazelcast reachable in this
environment. So every test builds a `Clients` object by hand -- mocks for llm,
embeddings, and oracle; a fake-but-truthy Neo4j double that answers every query with
"nothing"; no elastic or cache -- and wires it in through `get_clients`'s dependency
override, which is the one seam `src/clients/container.py` exists for. Nothing here
calls `Clients.build()` or runs the app lifespan, so no real network connection is ever
attempted.
"""

import os

# Must be set before `src` is imported anywhere: `create_app()` calls
# `setup_telemetry()` immediately, which reads this to skip installing OTel exporters
# and auto-instrumentation.
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.clients.container import Clients, get_clients
from src.core.config import get_settings
from src.main import create_app


@pytest.fixture
def settings_for_test(tmp_path):
    """The real `Settings` read from the repo's `.env`, with the registry file
    redirected to a tmp path so tests never touch the real `registry.json`."""
    return get_settings().model_copy(update={"REGISTRY_PATH": str(tmp_path / "registry.json")})


async def _fake_run(cypher: str, *, operation: str = "cypher", **params) -> list[dict]:
    """Reads return nothing, as against an empty graph. `upsert_edge` is the exception:
    it `RETURN r`s, and an empty result there means "an endpoint did not exist", which
    the route turns into a 404 -- so the happy path has to hand back a row."""
    if operation == "upsert_edge":
        return [{"r": {}}]
    return []


def _fake_neo4j() -> MagicMock:
    """A truthy stand-in for a connected `Neo4jClient`."""
    neo4j = MagicMock(name="Neo4jClient")
    neo4j.run = AsyncMock(side_effect=_fake_run)
    neo4j.run_many = AsyncMock(return_value=None)
    neo4j.scalar = AsyncMock(return_value=0)
    neo4j.close = AsyncMock(return_value=None)
    return neo4j


def build_clients(settings, *, neo4j: object | None) -> Clients:
    """A `Clients` dataclass instance with mock llm/embeddings/oracle and no
    elastic/cache -- neither is exercised by any route under test."""
    return Clients(
        settings=settings,
        llm=MagicMock(name="LLMClient"),
        embeddings=MagicMock(name="EmbeddingClient"),
        oracle=MagicMock(name="OracleEngineFactory"),
        neo4j=neo4j,
        elastic=None,
        cache=None,
    )


@pytest.fixture
def clients(settings_for_test) -> Clients:
    """The default fake container: Neo4j "connected" (but empty), nothing else."""
    return build_clients(settings_for_test, neo4j=_fake_neo4j())


@pytest.fixture
def clients_no_neo4j(settings_for_test) -> Clients:
    """Neo4j absent -- the graph-editor mutations must degrade the way the old code did."""
    return build_clients(settings_for_test, neo4j=None)


@pytest.fixture
def app(clients):
    """A fresh `create_app()` instance with `get_clients` overridden to the fakes.

    No lifespan runs against this app (plain `httpx.ASGITransport` requests don't
    trigger it), so `Clients.build()` is never called.
    """
    application = create_app()
    application.dependency_overrides[get_clients] = lambda: clients
    return application


@pytest.fixture
async def async_client(app):
    """An httpx client talking to `app` in-process, no sockets involved."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def client_factory():
    """For the tests that need a client wired to a *different* `Clients` object than
    the default `clients` fixture (e.g. `clients_no_neo4j`)."""

    @asynccontextmanager
    async def _make(clients_obj: Clients):
        application = create_app()
        application.dependency_overrides[get_clients] = lambda: clients_obj
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

    return _make

"""Request validation (via the live HTTP contract) and LLM response model validation.

Request-side assertions hit the actual routes, because "422" is a status code FastAPI
produces from `StrictModel`'s `extra="forbid"` and field constraints -- the behaviour
under test is the wiring, not just the pydantic model in isolation.

LLM-response-side assertions instantiate the models directly with example payloads
lifted from the prompt `.txt` files, so a schema change that no longer matches what the
prompt promises the LLM fails here.
"""

import pytest
from pydantic import ValidationError

from src.agents.onboarding.schemas import EntityExtraction, EntityKeyMap, TableSemantics
from src.agents.query.schemas import SqlPlan, SubQuestions, VisualizationSpec

# ============================================================== request validation


async def test_unknown_extra_field_is_422(async_client):
    resp = await async_client.post(
        "/api/v1/query", json={"question": "hi", "unexpected_field": "nope"}
    )
    assert resp.status_code == 422


async def test_empty_question_is_422(async_client):
    resp = await async_client.post("/api/v1/query", json={"question": ""})
    assert resp.status_code == 422


async def test_question_over_2000_chars_is_422(async_client):
    resp = await async_client.post("/api/v1/query", json={"question": "x" * 2001})
    assert resp.status_code == 422


async def test_question_at_2000_chars_is_accepted(async_client):
    resp = await async_client.post("/api/v1/query", json={"question": "x" * 2000})
    assert resp.status_code == 200


@pytest.mark.parametrize("node_type", ["Database", "Table", "Column", "Entity"])
async def test_create_node_known_types_accepted(async_client, node_type):
    resp = await async_client.post(
        "/api/v1/graph/node",
        json={"id": "n1", "name": "Node One", "type": node_type, "description": ""},
    )
    assert resp.status_code == 200


async def test_create_node_bogus_type_is_422(async_client):
    resp = await async_client.post(
        "/api/v1/graph/node",
        json={"id": "n1", "name": "Node One", "type": "Bogus", "description": ""},
    )
    assert resp.status_code == 422


async def test_create_edge_known_type_accepted(async_client):
    resp = await async_client.post(
        "/api/v1/graph/edge", json={"source": "a", "target": "b", "type": "HAS_TABLE"}
    )
    assert resp.status_code == 200


@pytest.mark.parametrize("bad_type", ["has-table", "lowercase"])
async def test_create_edge_bad_type_is_422(async_client, bad_type):
    resp = await async_client.post(
        "/api/v1/graph/edge", json={"source": "a", "target": "b", "type": bad_type}
    )
    assert resp.status_code == 422


async def test_onboard_connection_string_requires_driver_prefix(async_client):
    resp = await async_client.post(
        "/api/v1/onboard",
        json={"database_name": "Test DB", "connection_string": "host:1521/service"},
    )
    assert resp.status_code == 422


async def test_onboard_connection_string_with_driver_prefix_accepted(async_client):
    resp = await async_client.post(
        "/api/v1/onboard",
        json={
            "database_name": "Test DB",
            "connection_string": "oracle+oracledb_async://user:pass@host:1521/?service_name=x",
        },
    )
    assert resp.status_code == 200


# =========================================================== LLM response models


class TestSubQuestions:
    def test_realistic_example_validates(self):
        # Straight from decompose_query.txt's second EXAMPLE.
        payload = {
            "sub_questions": [
                "Show me all complaints for Bank 1",
                "What is the average inspection score for Bank 1?",
            ]
        }
        model = SubQuestions.model_validate(payload)
        assert model.sub_questions == payload["sub_questions"]

    def test_empty_list_raises(self):
        with pytest.raises(ValidationError):
            SubQuestions.model_validate({"sub_questions": []})

    def test_malformed_raises(self):
        with pytest.raises(ValidationError):
            SubQuestions.model_validate({"sub_questions": "not a list"})


class TestSqlPlan:
    def test_realistic_example_validates(self):
        # Shape from generate_sql.txt's Format block.
        payload = {"target_database_id": "db-123", "sql": "SELECT * FROM USERS"}
        model = SqlPlan.model_validate(payload)
        assert model.sql == "SELECT * FROM USERS"
        assert model.target_database_id == "db-123"

    def test_strips_sql_code_fence(self):
        payload = {"target_database_id": "db-123", "sql": "```sql\nSELECT * FROM USERS\n```"}
        model = SqlPlan.model_validate(payload)
        assert model.sql == "SELECT * FROM USERS"

    def test_missing_sql_raises(self):
        with pytest.raises(ValidationError):
            SqlPlan.model_validate({"target_database_id": "db-123"})

    def test_empty_sql_raises(self):
        with pytest.raises(ValidationError):
            SqlPlan.model_validate({"target_database_id": "db-123", "sql": ""})


class TestVisualizationSpec:
    def test_realistic_example_validates(self):
        # Shape from recommend_visualizations.txt's Format block.
        payload = {
            "is_visualizable": True,
            "spec": {
                "xAxis": {"data": ["Bank 1", "Bank 2"]},
                "series": [{"data": [10, 20]}],
            },
        }
        model = VisualizationSpec.model_validate(payload)
        assert model.is_visualizable is True
        assert model.spec == payload["spec"]

    def test_not_visualizable_without_spec_validates(self):
        model = VisualizationSpec.model_validate({"is_visualizable": False})
        assert model.spec is None

    def test_visualizable_without_spec_raises(self):
        with pytest.raises(ValidationError):
            VisualizationSpec.model_validate({"is_visualizable": True})

    def test_visualizable_with_empty_spec_raises(self):
        with pytest.raises(ValidationError):
            VisualizationSpec.model_validate({"is_visualizable": True, "spec": {}})


class TestTableSemantics:
    def test_realistic_example_validates(self):
        # From generate_semantics.txt's Example format.
        payload = {
            "table_name_1": (
                "Stores detailed records of financial transactions including "
                "amounts and timestamps."
            ),
            "table_name_2": (
                "Manages customer grievance tickets, their resolution status, "
                "and assigned officers."
            ),
        }
        model = TableSemantics.model_validate(payload)
        assert model.root == payload

    def test_non_string_value_raises(self):
        with pytest.raises(ValidationError):
            TableSemantics.model_validate({"table_name_1": {"nested": "not a string"}})


class TestEntityExtraction:
    def test_realistic_example_validates(self):
        # From identify_entities.txt's Return block.
        payload = {
            "entities": [
                {
                    "id": "CustomerGrievance",
                    "description": "A formal complaint raised by a customer.",
                    "mapped_tables": ["COMPLAINTS"],
                },
                {
                    "id": "BankOfficer",
                    "description": "An employee assigned to handle cases or inspections.",
                    "mapped_tables": ["COMPLAINTS", "INSPECTION_REPORTS"],
                },
            ],
            "relationships": [
                {"source": "BankOfficer", "target": "CustomerGrievance", "type": "INVESTIGATES"}
            ],
        }
        model = EntityExtraction.model_validate(payload)
        assert [e.id for e in model.entities] == ["CustomerGrievance", "BankOfficer"]
        assert model.relationships[0].type == "INVESTIGATES"

    def test_entity_missing_id_raises(self):
        with pytest.raises(ValidationError):
            EntityExtraction.model_validate(
                {"entities": [{"description": "no id here"}], "relationships": []}
            )


class TestEntityKeyMap:
    def test_realistic_example_validates(self):
        # From map_entity_columns.txt's Return block.
        payload = {
            "entities": [
                {
                    "id": "Customer",
                    "entity_keys": [{"table": "CUSTOMERS", "column": "CUSTOMER_ID"}],
                }
            ]
        }
        model = EntityKeyMap.model_validate(payload)
        assert model.entities[0].id == "Customer"
        assert model.entities[0].entity_keys[0].column == "CUSTOMER_ID"

    def test_entity_key_missing_column_raises(self):
        with pytest.raises(ValidationError):
            EntityKeyMap.model_validate(
                {"entities": [{"id": "Customer", "entity_keys": [{"table": "CUSTOMERS"}]}]}
            )

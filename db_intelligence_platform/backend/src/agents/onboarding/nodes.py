"""Onboarding LangGraph nodes.

One ``BaseNode`` subclass per node in the old ``admin_onboarding.py`` workflow, in the
same order. ``BaseNode.__call__`` already handles the "skip if a prior node failed" and
"turn a raised exception into a failure state" behaviour, so each ``run`` here is just
its documented happy path.
"""

from typing import Any

from src.agents.onboarding.schema_extractor import SchemaExtractor
from src.agents.onboarding.schemas import EntityExtraction, EntityKeyMap, TableSemantics
from src.agents.base import BaseNode
from src.schemas.domain import EntityRecord, Relationship, TableSchema
from src.services.graph_write import GraphWriteService
from src.services.search_service import SearchService
from src.utils.helpers import json_dumps, load_prompt, truncate

EXISTING_ENTITIES_QUERY = "MATCH (e:Entity) RETURN e.id AS id, e.description AS description LIMIT 50"
EXISTING_ENTITIES_LIMIT = 50


class ExtractSchemaNode(BaseNode):
    """Connects to the target DB and extracts table, column, and foreign key definitions."""

    agent = "onboarding"
    name = "extract_schema"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        extractor = SchemaExtractor()
        async with self.clients.oracle.connect(state["connection_string"]) as conn:
            tables = await extractor.extract(conn)
        self.log.info("Extracted %d tables", len(tables))
        return {
            "status": "extracted_schema",
            "extracted_schema": {"tables": [t.model_dump() for t in tables]},
        }


class GenerateSemanticsNode(BaseNode):
    """Uses LLM to generate semantic descriptions of tables and columns."""

    agent = "onboarding"
    name = "generate_semantics"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        tables = state["extracted_schema"].get("tables", [])
        prompt = load_prompt(
            "onboarding", "generate_semantics", schema_summary=json_dumps(_schema_summary(tables))
        )
        semantics = await self.clients.llm.complete_model(prompt, TableSemantics, operation=self.name)
        self.log.info("Semantics generated for %d tables", len(semantics.root))
        return {"status": "generated_semantics", "semantic_descriptions": semantics.root}


class IdentifyEntitiesNode(BaseNode):
    """Uses LLM to identify business entities and relationships from the schema."""

    agent = "onboarding"
    name = "identify_entities"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        tables = state["extracted_schema"].get("tables", [])
        existing_entities = await self._fetch_existing_entities()
        prompt = load_prompt(
            "onboarding",
            "identify_entities",
            existing_entities_context=json_dumps(existing_entities),
            schema_summary=json_dumps(_schema_summary(tables, state.get("semantic_descriptions", {}))),
        )
        extraction = await self.clients.llm.complete_model(prompt, EntityExtraction, operation=self.name)
        entities = [e.model_dump() for e in extraction.entities]
        relationships = [r.model_dump() for r in extraction.relationships]
        entities = self._ensure_full_table_coverage(entities, tables)
        self.log.info("Identified %d entities", len(entities))
        return {"status": "identified_entities", "entities": entities, "relationships": relationships}

    async def _fetch_existing_entities(self) -> list[dict[str, Any]]:
        if not self.clients.neo4j:
            return []
        try:
            return await self.clients.neo4j.run(
                EXISTING_ENTITIES_QUERY, operation="existing_entities"
            )
        except Exception as exc:
            self.log.warning("Could not fetch existing entities: %s", exc)
            return []

    def _ensure_full_table_coverage(
        self, entities: list[dict[str, Any]], tables: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Deterministic fallback: auto-generate an Entity for every table the LLM
        left unmapped, so onboarding always covers 100% of the schema."""
        mapped = {t.upper() for ent in entities for t in ent.get("mapped_tables", [])}
        for table in tables:
            table_name = table["name"]
            if table_name.upper() in mapped:
                continue
            self.log.debug("Auto-generating fallback Entity for unmapped table: %s", table_name)
            entities.append(
                {
                    "id": table_name.capitalize(),
                    "description": f"Core business entity containing records and details regarding {table_name}.",
                    "mapped_tables": [table_name],
                    "entity_keys": [],
                }
            )
        return entities


class MapEntityColumnsNode(BaseNode):
    """Takes the identified entities and maps physical column keys to them."""

    agent = "onboarding"
    name = "map_entity_columns"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        tables = state["extracted_schema"].get("tables", [])
        entities = state.get("entities", [])
        prompt = load_prompt(
            "onboarding",
            "map_entity_columns",
            schema_summary=json_dumps(
                [{"table": t["name"], "columns": [c["name"] for c in t["columns"]]} for t in tables]
            ),
            entities_summary=json_dumps(
                [{"id": e["id"], "mapped_tables": e.get("mapped_tables", [])} for e in entities]
            ),
        )
        result = await self.clients.llm.complete_model(prompt, EntityKeyMap, operation=self.name)
        key_map = {e.id: [k.model_dump() for k in e.entity_keys] for e in result.entities}
        for entity in entities:
            if entity["id"] in key_map:
                entity["entity_keys"] = key_map[entity["id"]]
        self.log.info("Entity keys mapped for %d entities", len(key_map))
        return {"status": "mapped_columns", "entities": entities}


class ConstructKnowledgeGraphNode(BaseNode):
    """Pushes the LLM-identified entities and relationships to Neo4j."""

    agent = "onboarding"
    name = "construct_knowledge_graph"

    def __init__(self, clients) -> None:
        super().__init__(clients)
        self.graph_write = GraphWriteService(clients)

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        entities_raw = state.get("entities", [])
        if not entities_raw:
            return {"status": "constructed_kg"}

        tables = [TableSchema.model_validate(t) for t in state["extracted_schema"].get("tables", [])]
        entities = [EntityRecord.model_validate(e) for e in entities_raw]
        relationships = [Relationship.model_validate(r) for r in state.get("relationships", [])]
        table_map = {t.name.upper(): t for t in tables}
        db_id = state.get("database_id", "unknown")

        await self.graph_write.merge_database(
            db_id, state.get("database_name", db_id), state.get("connection_string", "unknown")
        )
        await self.graph_write.merge_tables(db_id, tables)
        for table in tables:
            await self.graph_write.merge_columns(db_id, table)
        await self.graph_write.merge_entities(db_id, entities)
        for entity in entities:
            await self.graph_write.merge_entity_keys(db_id, entity, table_map)
        await self.graph_write.merge_relationships(relationships)

        self.log.info("Neo4j Knowledge Graph constructed")
        return {"status": "constructed_kg"}


class GenerateEmbeddingsNode(BaseNode):
    """Generates embeddings for abstract entities and indexes them for retrieval."""

    agent = "onboarding"
    name = "generate_embeddings"

    def __init__(self, clients) -> None:
        super().__init__(clients)
        self.search = SearchService(clients)

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        entities_raw = state.get("entities", [])
        if entities_raw:
            try:
                entities = [EntityRecord.model_validate(e) for e in entities_raw]
                await self.search.ensure_entity_index()
                await self.search.index_entities(state.get("database_id", "unknown"), entities)
                self.log.info("Indexed %d entity embeddings", len(entities))
            except Exception as exc:
                # Embedding failures never fail onboarding itself -- matches the old
                # node, which logged and returned "generated_embeddings" regardless.
                self.log.warning("Embedding indexing error: %s", exc)
        return {"status": "generated_embeddings"}


class RegisterMetadataNode(BaseNode):
    """Saves all gathered metadata into the centralized registry."""

    agent = "onboarding"
    name = "register_metadata"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        # Metadata registration is now handled reliably via Hazelcast in the onboarding
        # route/service, to avoid Oracle credential issues -- this node is a no-op.
        return {"status": "completed"}


def _schema_summary(
    tables: list[dict[str, Any]], semantics: dict[str, str] | None = None
) -> list[dict[str, Any]]:
    """The ``{table, [purpose,] columns: [{name, type, samples}]}`` shape both LLM
    prompts serialize -- shared so the two nodes don't drift."""
    summary = []
    for table in tables:
        entry: dict[str, Any] = {"table": table["name"]}
        if semantics is not None:
            entry["purpose"] = semantics.get(table["name"], "")
        entry["columns"] = [
            {"name": c["name"], "type": c.get("type", ""), "samples": truncate(c.get("sample_values"), 3)}
            for c in table["columns"]
        ]
        summary.append(entry)
    return summary

"""Write side of the knowledge graph.

Ported from ``admin_onboarding.py``'s ``construct_knowledge_graph_node`` (the merge
Cypher) and ``app/api/endpoints.py`` (the delete/cleanup and graph-editor Cypher). Split
into one method per statement group so each stays small, and so the onboarding agent
and the graph routes never contend for the same file.

Label and relationship-type values reaching the Cypher builders here are validated
against ``ALLOWED_LABELS`` / ``_REL_TYPE_RE`` before interpolation -- the only two
places in this service where a caller-supplied string is spliced into Cypher text
rather than passed as a bound parameter.
"""

import re

from src.clients.container import Clients
from src.core.logging import get_logger
from src.schemas.domain import EntityRecord, Relationship, TableSchema

logger = get_logger(__name__)

#: The only node labels that may be interpolated into a Cypher statement.
ALLOWED_LABELS = frozenset({"Database", "Table", "Column", "Entity"})

_REL_TYPE_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def _validate_label(label: str) -> str:
    if label not in ALLOWED_LABELS:
        raise ValueError(f"Invalid node label: {label!r}")
    return label


def _validate_rel_type(rel_type: str) -> str:
    value = str(rel_type or "").strip()
    if not _REL_TYPE_RE.match(value):
        raise ValueError(f"Invalid relationship type: {rel_type!r}")
    return value


class GraphWriteService:
    """All write and delete Cypher lives here."""

    def __init__(self, clients: Clients) -> None:
        self.clients = clients
        self.neo4j = clients.neo4j
        self._warned_no_neo4j = False

    def _warn_no_neo4j(self) -> bool:
        """Returns True (so callers can ``if self._warn_no_neo4j(): return``)."""
        if not self._warned_no_neo4j:
            logger.warning("Neo4j is not configured -- graph write skipped")
            self._warned_no_neo4j = True
        return True

    # --- knowledge-graph construction (onboarding) ---

    async def merge_database(self, database_id: str, name: str, connection_string: str) -> None:
        """Upsert the ``:Database`` root node."""
        if not self.neo4j:
            self._warn_no_neo4j()
            return
        await self.neo4j.run(
            "MERGE (db:Database {id: $id}) SET db.connection_string = $conn_str, db.name = $db_name",
            operation="merge_database",
            id=database_id,
            conn_str=connection_string,
            db_name=name,
        )

    async def merge_tables(self, database_id: str, tables: list[TableSchema]) -> None:
        """Upsert ``:Table`` nodes and their ``HAS_TABLE`` edges."""
        if not self.neo4j:
            self._warn_no_neo4j()
            return
        statements = [
            (
                "MERGE (t:Table {id: $t_id}) SET t.name = $t_name "
                "WITH t MATCH (db:Database {id: $db_id}) MERGE (db)-[:HAS_TABLE]->(t)",
                {"t_id": f"{database_id}_{table.name}", "t_name": table.name, "db_id": database_id},
            )
            for table in tables
        ]
        if statements:
            await self.neo4j.run_many(statements, operation="merge_tables")

    async def merge_columns(self, database_id: str, table: TableSchema) -> None:
        """Upsert ``:Column`` nodes with sample values, plus ``HAS_COLUMN`` edges."""
        if not self.neo4j:
            self._warn_no_neo4j()
            return
        statements = [
            (
                "MERGE (c:Column {id: $c_id}) SET c.name = $c_name, c.type = $c_type, "
                "c.sample_values = $c_samples "
                "WITH c MATCH (t:Table {id: $t_id}) MERGE (t)-[:HAS_COLUMN]->(c)",
                {
                    "c_id": f"{database_id}_{table.name}_{col.name}",
                    "c_name": col.name,
                    "c_type": col.type,
                    "c_samples": _sample_values(col.name, table.sample_data),
                    "t_id": f"{database_id}_{table.name}",
                },
            )
            for col in table.columns
        ]
        if statements:
            await self.neo4j.run_many(statements, operation="merge_columns")

    async def merge_entities(self, database_id: str, entities: list[EntityRecord]) -> None:
        """Upsert ``:Entity`` nodes and their ``CONTAINS`` edges from the database."""
        if not self.neo4j:
            self._warn_no_neo4j()
            return
        statements = [
            (
                "MERGE (e:Entity {id: $e_id}) SET e.name = $e_name, e.description = $desc "
                "WITH e MATCH (db:Database {id: $db_id}) MERGE (db)-[:CONTAINS]->(e)",
                {"e_id": entity.id, "e_name": entity.id, "desc": entity.description, "db_id": database_id},
            )
            for entity in entities
        ]
        if statements:
            await self.neo4j.run_many(statements, operation="merge_entities")

    async def merge_entity_keys(
        self, database_id: str, entity: EntityRecord, tables: dict[str, TableSchema]
    ) -> None:
        """Link tables to an entity (``MAPS_TO``) and mark its key columns (``REPRESENTS``)."""
        if not self.neo4j:
            self._warn_no_neo4j()
            return
        statements = []
        for table_name in entity.mapped_tables:
            table = tables.get(table_name.upper())
            if table is None:
                continue
            statements.append(self._maps_to_statement(database_id, table, entity))
            statements.extend(self._represents_statements(database_id, table, entity, table_name))
        if statements:
            await self.neo4j.run_many(statements, operation="merge_entity_keys")

    def _maps_to_statement(
        self, database_id: str, table: TableSchema, entity: EntityRecord
    ) -> tuple[str, dict]:
        return (
            "MATCH (t:Table {id: $t_id}) MATCH (e:Entity {id: $e_id}) MERGE (t)-[:MAPS_TO]->(e)",
            {"t_id": f"{database_id}_{table.name}", "e_id": entity.id},
        )

    def _represents_statements(
        self, database_id: str, table: TableSchema, entity: EntityRecord, table_name: str
    ) -> list[tuple[str, dict]]:
        statements = []
        for key in entity.keys_for_table(table_name):
            column = table.column_named(key.column)
            col_name = column.name if column else key.column
            statements.append(
                (
                    "MATCH (c:Column {id: $c_id}) SET c.is_entity_key = true, c.represented_entity = $e_id "
                    "WITH c MATCH (e:Entity {id: $e_id}) MERGE (c)-[:REPRESENTS]->(e)",
                    {"c_id": f"{database_id}_{table.name}_{col_name}", "e_id": entity.id},
                )
            )
        return statements

    async def merge_relationships(self, relationships: list[Relationship]) -> None:
        """Upsert entity-to-entity edges. A relationship with an invalid type is
        skipped and logged rather than aborting the rest -- matching the old code's
        best-effort behaviour."""
        if not self.neo4j:
            self._warn_no_neo4j()
            return
        statements = []
        for rel in relationships:
            try:
                rel_type = _validate_rel_type(rel.type)
            except ValueError as exc:
                logger.warning("%s", exc)
                continue
            statements.append(
                (
                    f"MATCH (src:Entity {{id: $source}}) MATCH (tgt:Entity {{id: $target}}) "
                    f"MERGE (src)-[:`{rel_type}`]->(tgt)",
                    {"source": str(rel.source).strip(), "target": str(rel.target).strip()},
                )
            )
        if not statements:
            return
        try:
            await self.neo4j.run_many(statements, operation="merge_relationships")
        except Exception as exc:
            logger.warning("Failed to merge relationships: %s", exc)

    # --- deletion (routes) ---

    async def delete_database_footprint(self, database_id: str) -> None:
        """Remove one database's tables, columns, entity links, and orphaned entities."""
        if not self.neo4j:
            self._warn_no_neo4j()
            return
        statements = [
            (
                "MATCH (db:Database {id: $db_id})-[:HAS_TABLE]->(t:Table) "
                "OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column) "
                "DETACH DELETE t, c",
                {"db_id": database_id},
            ),
            (
                "MATCH (db:Database {id: $db_id})-[r:CONTAINS]->(e:Entity) DELETE r",
                {"db_id": database_id},
            ),
            (
                "MATCH (e:Entity) WHERE NOT (e)<-[:CONTAINS]-() DETACH DELETE e",
                {},
            ),
            (
                "MATCH (db:Database {id: $db_id}) DETACH DELETE db",
                {"db_id": database_id},
            ),
        ]
        try:
            await self.neo4j.run_many(statements, operation="delete_database_footprint")
        except Exception as exc:
            logger.warning("Neo4j delete error: %s", exc)

    async def delete_entities_for_database(self, database_id: str) -> None:
        """Pre-onboarding cleanup: drop the previous footprint to avoid duplicates."""
        if not self.neo4j:
            self._warn_no_neo4j()
            return
        try:
            await self.neo4j.run(
                "MATCH (db:Database {id: $db_id})-[:CONTAINS]->(e:Entity) DETACH DELETE db, e",
                operation="delete_entities_for_database",
                db_id=database_id,
            )
        except Exception as exc:
            logger.warning("Cleanup Neo4j error: %s", exc)

    async def clear_all(self) -> None:
        """Drop every node and relationship. Backs ``DELETE /graph/clear``."""
        if not self.neo4j:
            self._warn_no_neo4j()
            return
        try:
            await self.neo4j.run("MATCH (n) DETACH DELETE n", operation="clear_all")
        except Exception as exc:
            logger.warning("Clear graph error: %s", exc)

    async def upsert_node(self, node_id: str, name: str, label: str, description: str) -> None:
        """Manual node creation from the graph editor. ``label`` must be in ALLOWED_LABELS."""
        if not self.neo4j:
            self._warn_no_neo4j()
            return
        safe_label = _validate_label(label)
        query = (
            f"MERGE (n:{safe_label} {{id: $id}}) "
            "SET n.name = $name, n.label = $name, n.description = $desc RETURN n"
        )
        await self.neo4j.run(query, operation="upsert_node", id=node_id, name=name, desc=description)

    async def upsert_edge(self, source: str, target: str, rel_type: str) -> bool:
        """Manual edge creation from the graph editor.

        Returns whether the edge exists after the call. Both endpoints are ``MATCH``ed,
        never merged, so a missing one makes the whole statement match nothing and the
        ``MERGE`` never runs -- the caller must report that instead of a false success.
        """
        if not self.neo4j:
            self._warn_no_neo4j()
            return False
        safe_type = _validate_rel_type(str(rel_type).upper().replace("`", ""))
        query = (
            "MATCH (src) WHERE src.id = $source "
            "MATCH (tgt) WHERE tgt.id = $target "
            f"MERGE (src)-[r:{safe_type}]->(tgt) RETURN r"
        )
        records = await self.neo4j.run(
            query, operation="upsert_edge", source=source, target=target
        )
        return bool(records)

    async def delete_node(self, node_id: str) -> None:
        if not self.neo4j:
            self._warn_no_neo4j()
            return
        await self.neo4j.run(
            "MATCH (n) WHERE n.id = $id DETACH DELETE n", operation="delete_node", id=node_id
        )

    async def delete_edge(self, source: str, target: str, rel_type: str) -> None:
        if not self.neo4j:
            self._warn_no_neo4j()
            return
        safe_type = _validate_rel_type(str(rel_type).upper().replace("`", ""))
        query = (
            f"MATCH (src)-[r:{safe_type}]->(tgt) "
            "WHERE src.id = $src_id AND tgt.id = $tgt_id DELETE r"
        )
        await self.neo4j.run(query, operation="delete_edge", src_id=source, tgt_id=target)


def _sample_values(col_name: str, sample_data: list[dict]) -> list[str]:
    """Distinct, string-coerced, order-preserving sample values for one column."""
    values: list[str] = []
    for row in sample_data:
        val = row.get(col_name)
        if val is not None and str(val) not in values:
            values.append(str(val))
    return values

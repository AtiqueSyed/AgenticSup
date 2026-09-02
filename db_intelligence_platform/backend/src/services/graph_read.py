"""Read side of the knowledge graph.

Ported from ``app/agents/user_query.py``'s ``retrieve_context_node`` (the three schema
Cypher variants) and ``app/api/endpoints.py``'s ``get_knowledge_graph`` / entity-count
queries. Every method returns validated models or plain JSON-ready dicts; no caller ever
sees a Neo4j record object.
"""

from typing import Any

from src.clients.container import Clients
from src.core.logging import get_logger
from src.schemas.domain import DatabaseSchema

logger = get_logger(__name__)

#: Placeholder database id the frontend sends before the user has picked one -- treated
#: the same as "no database selected".
UNSELECTED_DATABASE = "selected-db-id"

# The three old Cypher variants differ only in their opening MATCH clause: whether the
# database is pinned by id, whether an entity filter is present at all, and which
# condition keeps a column beyond the "five or fewer" cutoff. Everything else -- the
# column projection and the RETURN shape -- is identical, so it is built once here.
_COLUMN_PROJECTION = (
    "[col IN all_columns WHERE col_count <= 5 OR {condition} | "
    "{{name: col.name, type: col.type, description: col.description, "
    "sample_values: col.sample_values, is_entity_key: col.is_entity_key}}] AS columns"
)
_RETURN_CLAUSE = (
    "RETURN db.id AS database_id, db.name AS database_name, db.connection_string AS conn_str, "
    "collect({name: t.name, columns: columns}) AS tables"
)

_SCOPED_ENTITY_OPENING = (
    "MATCH (db:Database {id: $db_id})\n"
    "MATCH (e:Entity) WHERE e.id IN $matched_entities\n"
    "MATCH (db)-[:HAS_TABLE]->(t:Table)-[:MAPS_TO]->(e)\n"
)
_GLOBAL_ENTITY_OPENING = (
    "MATCH (e:Entity) WHERE e.id IN $matched_entities\n"
    "MATCH (db:Database)-[:HAS_TABLE]->(t:Table)-[:MAPS_TO]->(e)\n"
)
_ENTITY_COLUMN_CONDITION = "EXISTS((col)-[:REPRESENTS]->(e))"

_ALL_SCHEMAS_CYPHER = (
    "MATCH (db:Database)-[:HAS_TABLE]->(t:Table)\n"
    "OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column)\n"
    "WITH db, t, collect(c) AS all_columns, count(c) AS col_count\n"
    f"WITH db, t, {_COLUMN_PROJECTION.format(condition='col.is_entity_key = true')}\n"
    f"{_RETURN_CLAUSE}"
)

_SCOPED_NODES_CYPHER = """
MATCH (db:Database {id: $db_id})
OPTIONAL MATCH (db)-[:HAS_TABLE]->(t:Table)
OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column)
OPTIONAL MATCH (db)-[:CONTAINS]->(e:Entity)
WITH collect(db) + collect(t) + collect(c) + collect(e) AS raw_nodes
UNWIND raw_nodes AS n
WITH DISTINCT n
WHERE n IS NOT NULL
RETURN n.id AS id,
       coalesce(n.label, n.name, n.id) AS label,
       labels(n)[0] AS type
"""
_SCOPED_EDGES_CYPHER = """
MATCH (db:Database {id: $db_id})
OPTIONAL MATCH (db)-[:HAS_TABLE]->(t:Table)
OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column)
OPTIONAL MATCH (db)-[:CONTAINS]->(e:Entity)
WITH collect(db.id) + collect(t.id) + collect(c.id) + collect(e.id) AS node_ids
MATCH (src)-[r]->(tgt)
WHERE src.id IN node_ids AND tgt.id IN node_ids
RETURN DISTINCT src.id AS source, tgt.id AS target, type(r) AS type
"""
_GLOBAL_NODES_CYPHER = (
    "MATCH (n) WHERE n:Entity OR n:Database OR n:Table OR n:Column "
    "RETURN n.id AS id, coalesce(n.label, n.name, n.id) AS label, labels(n)[0] AS type"
)
_GLOBAL_EDGES_CYPHER = "MATCH (src)-[r]->(tgt) RETURN src.id AS source, tgt.id AS target, type(r) AS type"


def _is_scoped(database_id: str | None) -> bool:
    return bool(database_id) and database_id != UNSELECTED_DATABASE


def _entity_schema_query(database_id: str | None) -> str:
    """Shared body for the entity-scoped lookup -- only the opening MATCH differs."""
    opening = _SCOPED_ENTITY_OPENING if _is_scoped(database_id) else _GLOBAL_ENTITY_OPENING
    return (
        f"{opening}"
        "OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column)\n"
        "WITH db, t, e, collect(c) AS all_columns, count(c) AS col_count\n"
        f"WITH db, t, {_COLUMN_PROJECTION.format(condition=_ENTITY_COLUMN_CONDITION)}\n"
        f"{_RETURN_CLAUSE}"
    )


def _to_nodes(raw_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": n["id"],
            "type": "input" if n["type"] == "Database" else "default",
            "data": {"label": f"[{n['type']}]\n{n['label']}"},
            "position": {"x": 0, "y": 0},
        }
        for n in raw_nodes
        if n.get("id")
    ]


def _to_edges(raw_edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": f"{e['source']}-{e['target']}-{e['type']}",
            "source": e["source"],
            "target": e["target"],
            "label": e["type"],
            "animated": e["type"] != "CONTAINS",
        }
        for e in raw_edges
        if e.get("source") and e.get("target")
    ]


class GraphReadService:
    """All read Cypher lives here."""

    def __init__(self, clients: Clients) -> None:
        self.clients = clients
        self.neo4j = clients.neo4j

    async def count_entities(self) -> int:
        """Number of ``:Entity`` nodes. Backs ``/stats.entities_identified``."""
        if not self.neo4j:
            return 0
        return await self.neo4j.scalar(
            "MATCH (n:Entity) RETURN count(n) AS c", "c", default=0, operation="count_entities"
        )

    async def schemas_for_entities(
        self, entity_ids: list[str], database_id: str | None = None
    ) -> list[DatabaseSchema]:
        """Databases/tables/columns reachable from the matched entities.

        ``database_id`` scopes the search to one onboarded database (unless it is the
        frontend's "nothing selected" placeholder); ``None`` searches all of them.
        Returns ``[]`` when nothing matches -- the caller decides whether to fall back
        to ``all_schemas``.
        """
        if not self.neo4j or not entity_ids:
            return []
        params: dict[str, Any] = {"matched_entities": entity_ids}
        if _is_scoped(database_id):
            params["db_id"] = database_id
        records = await self.neo4j.run(
            _entity_schema_query(database_id), operation="schemas_for_entities", **params
        )
        return [DatabaseSchema.model_validate(r) for r in records]

    async def all_schemas(self) -> list[DatabaseSchema]:
        """Fallback used when entity matching finds nothing."""
        if not self.neo4j:
            return []
        records = await self.neo4j.run(_ALL_SCHEMAS_CYPHER, operation="all_schemas")
        return [DatabaseSchema.model_validate(r) for r in records]

    async def graph_nodes_and_edges(self, database_id: str | None = None) -> dict[str, Any]:
        """React-Flow payload for ``GET /graph``.

        Node ``data.label`` is ``"[Type]\\nLabel"``, and an edge is animated when its
        type is not ``CONTAINS`` -- the frontend depends on this shape byte-for-byte.
        """
        if not self.neo4j:
            return {"nodes": [], "edges": []}
        if database_id:
            raw_nodes = await self.neo4j.run(_SCOPED_NODES_CYPHER, operation="graph_nodes", db_id=database_id)
            raw_edges = await self.neo4j.run(_SCOPED_EDGES_CYPHER, operation="graph_edges", db_id=database_id)
        else:
            raw_nodes = await self.neo4j.run(_GLOBAL_NODES_CYPHER, operation="graph_nodes")
            raw_edges = await self.neo4j.run(_GLOBAL_EDGES_CYPHER, operation="graph_edges")
        return {"nodes": _to_nodes(raw_nodes), "edges": _to_edges(raw_edges)}

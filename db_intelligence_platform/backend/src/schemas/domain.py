"""Domain models -- the typed shapes that flow between services and agents.

These replace the bare dicts the old code passed around. Anything read out of Oracle's
inspector, Neo4j, or Elasticsearch is validated into one of these at the boundary, so a
Cypher change that drops a field fails loudly instead of surfacing as a missing key
several nodes later.
"""

from typing import Any

from pydantic import Field

from src.schemas.base import LenientModel


class ColumnSchema(LenientModel):
    """A physical column, as extracted from the source database or read back from Neo4j."""

    name: str
    type: str = "unknown"
    description: str | None = None
    sample_values: list[str] = Field(default_factory=list)
    is_entity_key: bool = False


class TableSchema(LenientModel):
    """A physical table plus the sample rows used to ground the LLM."""

    name: str
    columns: list[ColumnSchema] = Field(default_factory=list)
    foreign_keys: list[dict[str, Any]] = Field(default_factory=list)
    sample_data: list[dict[str, Any]] = Field(default_factory=list)

    def column_named(self, name: str) -> ColumnSchema | None:
        """Case-insensitive lookup -- Oracle identifiers arrive in mixed case."""
        target = name.upper()
        return next((c for c in self.columns if c.name.upper() == target), None)


class DatabaseSchema(LenientModel):
    """One onboarded database and the tables reachable from it."""

    database_id: str
    database_name: str = ""
    conn_str: str | None = None
    tables: list[TableSchema] = Field(default_factory=list)


class EntityKey(LenientModel):
    """The physical column that represents a business entity in a given table."""

    table: str
    column: str


class Relationship(LenientModel):
    """A directed edge between two business entities."""

    source: str
    target: str
    type: str = "RELATES_TO"


class EntityRecord(LenientModel):
    """A business entity: the abstract concept the knowledge graph is built from."""

    id: str = Field(min_length=1)
    description: str = ""
    mapped_tables: list[str] = Field(default_factory=list)
    entity_keys: list[EntityKey] = Field(default_factory=list)

    def keys_for_table(self, table: str) -> list[EntityKey]:
        target = table.upper()
        return [k for k in self.entity_keys if k.table.upper() == target]

"""Oracle schema introspection.

Ported from the old ``extract_schema_node``'s nested ``get_schema(conn)`` -- one
60-line function with three nested loops and three try/excepts. Split into small
methods here so each stays well under the complexity limit, but the logic and its
error handling are unchanged: a failing schema is skipped and logged, a failing
sample-row fetch yields an empty sample list, nothing else is swallowed.
"""

from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.engine.reflection import Inspector

from src.core.logging import get_logger
from src.schemas.domain import ColumnSchema, TableSchema

logger = get_logger(__name__)

#: Oracle system/sample schemas that are never user data -- copied verbatim from the
#: old ``exclude_schemas`` set.
EXCLUDED_SCHEMAS = frozenset(
    {
        "SYS", "SYSTEM", "XDB", "CTXSYS", "MDSYS", "DBSNMP", "OUTLN", "APPQOSSYS",
        "DVSYS", "DVF", "AUDSYS", "OJVMSYS", "GSMADMIN_INTERNAL", "ORDSYS", "OLAPSYS",
        "WMSYS", "SYSRAC", "SYSKM", "SYSDG", "SYSBACKUP", "SYS$UMF",
        "REMOTE_SCHEDULER_AGENT", "DIP", "GSMCATUSER", "GSMUSER", "XS$NULL",
        "ANONYMOUS", "FLOWS_FILES", "HR", "OE", "PM", "SH", "IX", "BI",
    }
)

SAMPLE_ROW_LIMIT = 3


class SchemaExtractor:
    """Introspects an Oracle connection into validated ``TableSchema`` objects."""

    def list_schemas(self, inspector: Inspector) -> list[str | None]:
        """``None`` (the connection's default schema) plus every non-system schema."""
        schemas: list[str | None] = [None]
        try:
            for name in inspector.get_schema_names():
                if name.upper() not in EXCLUDED_SCHEMAS and not name.upper().startswith("APEX"):
                    schemas.append(name)
        except Exception as exc:
            logger.warning("Could not list schemas: %s", exc)
        return list(dict.fromkeys(schemas))

    def list_tables(self, inspector: Inspector, schema: str | None) -> list[str]:
        return inspector.get_table_names(schema=schema)

    def describe_columns(
        self, inspector: Inspector, table: str, schema: str | None
    ) -> list[ColumnSchema]:
        return [
            ColumnSchema(name=col["name"], type=str(col["type"]))
            for col in inspector.get_columns(table, schema=schema)
        ]

    def sample_rows(self, conn: Connection, table: str, schema: str | None) -> list[dict[str, Any]]:
        """Up to three rows, to ground the LLM and prevent hallucinated values."""
        qualified = f"{schema}.{table}" if schema else table
        query = f"SELECT * FROM {qualified} FETCH FIRST {SAMPLE_ROW_LIMIT} ROWS ONLY"
        try:
            result = conn.execute(text(query))
            return [dict(row._mapping) for row in result]
        except Exception as exc:
            logger.debug("Could not fetch samples for %s: %s", table, exc)
            return []

    async def extract(self, conn) -> list[TableSchema]:
        """Runs the sync inspector/DBAPI work on ``conn`` and validates the result."""
        raw_tables = await conn.run_sync(self._extract_sync)
        return [TableSchema.model_validate(table) for table in raw_tables]

    def _extract_sync(self, sync_conn: Connection) -> list[dict[str, Any]]:
        inspector = sa_inspect(sync_conn)
        seen_tables: set[str] = set()
        tables: list[dict[str, Any]] = []
        for schema in self.list_schemas(inspector):
            tables.extend(self._extract_schema_tables(inspector, sync_conn, schema, seen_tables))
        return tables

    def _extract_schema_tables(
        self,
        inspector: Inspector,
        sync_conn: Connection,
        schema: str | None,
        seen_tables: set[str],
    ) -> list[dict[str, Any]]:
        """One wide try, matching the old code: an error mid-schema keeps whatever
        tables were already described and moves on to the next schema."""
        results: list[dict[str, Any]] = []
        try:
            for table_name in self.list_tables(inspector, schema):
                if table_name in seen_tables:
                    continue
                seen_tables.add(table_name)
                results.append(self._describe_table(inspector, sync_conn, table_name, schema))
        except Exception as exc:
            logger.warning("Skipping tables in schema %s: %s", schema, exc)
        return results

    def _describe_table(
        self, inspector: Inspector, sync_conn: Connection, table_name: str, schema: str | None
    ) -> dict[str, Any]:
        return {
            "name": table_name,
            "columns": self.describe_columns(inspector, table_name, schema),
            "foreign_keys": inspector.get_foreign_keys(table_name, schema=schema),
            "sample_data": self.sample_rows(sync_conn, table_name, schema),
        }

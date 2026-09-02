"""Neo4j client.

There is no official OTel instrumentation for the neo4j driver, so every query is
wrapped in a manual span here. That makes this the only place in the codebase allowed
to touch a driver session -- services call ``run`` / ``run_many``, never the driver.
"""

from typing import Any

from neo4j import AsyncGraphDatabase

from src.core.config import Settings
from src.core.logging import get_logger
from src.core.telemetry import get_tracer

logger = get_logger(__name__)
tracer = get_tracer(__name__)


class Neo4jClient:
    """Async Neo4j access with a span per query."""

    def __init__(self, driver: Any) -> None:
        self._driver = driver

    @classmethod
    def create(cls, settings: Settings) -> "Neo4jClient | None":
        """Returns ``None`` when the driver cannot be built, so the app still starts."""
        try:
            driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD.get_secret_value()),
            )
        except Exception:
            logger.exception("Failed to initialise Neo4j driver")
            return None
        return cls(driver)

    async def run(self, cypher: str, *, operation: str = "cypher", **params: Any) -> list[dict]:
        """Execute one statement and return its records as dicts."""
        with tracer.start_as_current_span(
            f"neo4j.{operation}",
            attributes={"db.system": "neo4j", "db.operation": operation},
        ):
            async with self._driver.session() as session:
                result = await session.run(cypher, **params)
                return await result.data()

    async def run_many(self, statements: list[tuple[str, dict]], *, operation: str) -> None:
        """Execute a batch in one session -- used by the knowledge-graph writer, where
        opening a session per MERGE was a measurable cost."""
        with tracer.start_as_current_span(
            f"neo4j.{operation}",
            attributes={"db.system": "neo4j", "db.statements": len(statements)},
        ):
            async with self._driver.session() as session:
                for cypher, params in statements:
                    await session.run(cypher, **params)

    async def scalar(self, cypher: str, key: str, *, default: Any = 0, **params: Any) -> Any:
        """Single value from a single record -- counts, existence checks."""
        records = await self.run(cypher, operation="scalar", **params)
        if not records:
            return default
        return records[0].get(key, default)

    async def close(self) -> None:
        await self._driver.close()

"""The client container.

The old ``app/core/database.py`` built five network clients at import time, which made
the module unimportable without a live cluster. Everything now hangs off one ``Clients``
object built during the app lifespan and reached through the ``get_clients`` dependency,
which is also what lets tests override the whole set with fakes.

Each client is optional: an unreachable Neo4j or Hazelcast degrades that feature rather
than preventing startup, matching the behaviour the platform already relied on.
"""

from dataclasses import dataclass

from src.clients.cache import CacheClient
from src.clients.elastic import ElasticClient
from src.clients.embeddings import EmbeddingClient
from src.clients.llm import LLMClient
from src.clients.neo4j import Neo4jClient
from src.clients.oracle import OracleEngineFactory
from src.core.config import Settings
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class Clients:
    """Every external dependency the services need, in one injectable object."""

    settings: Settings
    llm: LLMClient
    embeddings: EmbeddingClient
    oracle: OracleEngineFactory
    neo4j: Neo4jClient | None = None
    elastic: ElasticClient | None = None
    cache: CacheClient | None = None

    @classmethod
    def build(cls, settings: Settings) -> "Clients":
        return cls(
            settings=settings,
            llm=LLMClient(settings),
            embeddings=EmbeddingClient(settings),
            oracle=OracleEngineFactory(settings),
            neo4j=Neo4jClient.create(settings),
            elastic=ElasticClient.create(settings),
            cache=CacheClient.create(settings),
        )

    async def close(self) -> None:
        """Best-effort shutdown -- one failing client must not block the others."""
        await _close_async(self.llm, "llm")
        await _close_async(self.neo4j, "neo4j")
        await _close_async(self.elastic, "elastic")
        if self.cache:
            _close_sync(self.cache, "cache")


async def _close_async(client: object | None, name: str) -> None:
    if client is None:
        return
    try:
        await client.close()
    except Exception:
        logger.exception("Error closing %s client", name)


def _close_sync(client: object, name: str) -> None:
    try:
        client.close()
    except Exception:
        logger.exception("Error closing %s client", name)


# Populated by the lifespan handler; read through ``get_clients``.
_clients: Clients | None = None


def set_clients(clients: Clients | None) -> None:
    global _clients
    _clients = clients


def get_clients() -> Clients:
    """FastAPI dependency. Override this in tests to inject fakes."""
    if _clients is None:
        raise RuntimeError("Clients are not initialised -- is the app lifespan running?")
    return _clients

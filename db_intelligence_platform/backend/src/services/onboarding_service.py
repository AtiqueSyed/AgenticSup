"""Orchestrates the admin onboarding workflow.

Registers a database (deterministic id, same as the old code), wipes any prior
footprint left by a previous onboarding of the same connection string, and -- as a
background task -- runs the onboarding LangGraph and records its final status.
"""

import hashlib

from src.agents.onboarding.graph import build_onboarding_graph
from src.clients.container import Clients
from src.core.logging import get_logger
from src.services.graph_write import GraphWriteService
from src.services.registry_service import DatabaseRegistry
from src.services.search_service import SearchService

logger = get_logger(__name__)


class OnboardingService:
    def __init__(self, clients: Clients) -> None:
        self.clients = clients
        self.registry = DatabaseRegistry(clients.settings.REGISTRY_PATH)
        self.graph_write = GraphWriteService(clients)
        self.search = SearchService(clients)

    @staticmethod
    def database_id_for(connection_string: str) -> str:
        """Deterministic id so re-onboarding the same connection reuses it."""
        return hashlib.md5(connection_string.encode()).hexdigest()

    async def start(self, database_name: str, connection_string: str) -> str:
        """Register the database and wipe its prior footprint. Returns the database id."""
        db_id = self.database_id_for(connection_string)
        self.registry.add(db_id, database_name, connection_string)
        await self._wipe_prior_footprint(db_id)
        return db_id

    async def _wipe_prior_footprint(self, db_id: str) -> None:
        """Best-effort cleanup -- a failure here must not block onboarding."""
        try:
            await self.graph_write.delete_entities_for_database(db_id)
        except Exception:
            logger.exception("Failed to wipe prior Neo4j footprint for %s", db_id)
        try:
            await self.search.delete_database_documents(db_id)
        except Exception:
            logger.exception("Failed to wipe prior search footprint for %s", db_id)

    async def run(self, db_id: str, database_name: str, connection_string: str) -> None:
        """Runs as a ``BackgroundTasks`` job: invoke the onboarding graph, track status."""
        self.registry.set_status(db_id, "running")
        initial_state = {
            "database_id": db_id,
            "database_name": database_name,
            "connection_string": connection_string,
            "extracted_schema": {},
            "semantic_descriptions": {},
            "entities": [],
            "relationships": [],
            "status": "started",
            "errors": [],
        }
        try:
            graph = build_onboarding_graph(self.clients)
            final_state = await graph.ainvoke(initial_state)
            self.registry.set_status(db_id, final_state.get("status", "completed"))
        except Exception as exc:
            logger.exception("Onboarding failed for %s", db_id)
            self.registry.set_status(db_id, f"failed: {exc}")

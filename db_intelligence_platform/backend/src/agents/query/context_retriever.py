"""Thin orchestration between entity search and schema resolution.

The old ``retrieve_context_node`` embedded sub-questions, ran a kNN search, and then
picked between three near-identical Cypher queries inline -- the second-worst
complexity offender in the old agent. That branching now lives in ``GraphReadService``
(``schemas_for_entities`` / ``all_schemas``); this class is just the two-step call
sequence the node needs.
"""

from src.clients.container import Clients
from src.core.logging import get_logger
from src.schemas.domain import DatabaseSchema
from src.services.graph_read import GraphReadService
from src.services.search_service import SearchService

logger = get_logger(__name__)


class ContextRetriever:
    def __init__(self, clients: Clients) -> None:
        self._search = SearchService(clients)
        self._graph = GraphReadService(clients)

    async def match_entities(self, sub_questions: list[str]) -> list[str]:
        """Entity ids matched from Elasticsearch, one kNN search per sub-question."""
        return await self._search.match_entity_ids(sub_questions)

    async def resolve(self, database_id: str | None, entity_ids: list[str]) -> list[DatabaseSchema]:
        """Schemas reachable from the matched entities, falling back to every schema
        when nothing matches -- preserves the old node's fallback exactly."""
        schemas = await self._graph.schemas_for_entities(entity_ids, database_id)
        if schemas:
            return schemas
        return await self._graph.all_schemas()

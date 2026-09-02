"""Orchestrates the user-query workflow.

Loads chat history from the cache (Hazelcast), runs the query LangGraph, appends the
new turn to history and writes it back, and shapes the result into ``QueryResponse``.
"""

from typing import Any

from src.agents.query.graph import build_query_graph
from src.clients.container import Clients
from src.core.logging import get_logger
from src.schemas.query import QueryResponse
from src.services.registry_service import DatabaseRegistry

logger = get_logger(__name__)

#: Placeholder id the frontend sends before a real database has been selected.
_UNSELECTED_DB_SENTINEL = "selected-db-id"


class QueryService:
    def __init__(self, clients: Clients) -> None:
        self.clients = clients
        self.registry = DatabaseRegistry(clients.settings.REGISTRY_PATH)

    @staticmethod
    def _session_id(database_id: str | None) -> str:
        return f"chat_{database_id}" if database_id else "chat_global"

    def _connection_string(self, database_id: str | None) -> str | None:
        if not database_id or database_id == _UNSELECTED_DB_SENTINEL:
            return None
        return self.registry.connection_string_for(database_id)

    def _build_relevant_context(
        self, chat_history: list[dict[str, Any]], conn_str: str | None
    ) -> dict[str, Any]:
        context: dict[str, Any] = {"chat_history": chat_history}
        if conn_str:
            context["connection_string"] = conn_str
        return context

    async def ask(self, database_id: str | None, question: str) -> QueryResponse:
        session_id = self._session_id(database_id)
        cache = self.clients.cache
        chat_history = cache.get_json("chat_sessions", session_id, default=[]) if cache else []

        initial_state = {
            "question": question,
            "database_id": database_id,
            "relevant_context": self._build_relevant_context(
                chat_history, self._connection_string(database_id)
            ),
            "generated_sql": None,
            "query_results": None,
            "validation_error": None,
            "synthesized_answer": None,
            "recommended_visualizations": None,
            "iterations": 0,
        }

        graph = build_query_graph(self.clients)
        final_state = await graph.ainvoke(initial_state)

        if cache:
            chat_history.append({"q": question, "a": final_state.get("synthesized_answer", "")})
            cache.put_json("chat_sessions", session_id, chat_history)

        return QueryResponse(
            database_id=final_state.get("database_id"),
            database_name=final_state.get("database_name"),
            answer=final_state.get("synthesized_answer", "Error synthesizing answer"),
            sql_used=final_state.get("generated_sql"),
            visualizations=final_state.get("recommended_visualizations"),
            results=final_state.get("query_results"),
        )

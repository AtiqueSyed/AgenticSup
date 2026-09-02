"""Compiled user-query workflow.

The factory signature is fixed here because ``services/query_service.py`` imports it.
"""

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.query.nodes import (
    DecomposeQueryNode,
    ExecuteSqlNode,
    GenerateSqlNode,
    RecommendVisualizationsNode,
    RetrieveContextNode,
    SynthesizeAnswerNode,
    ValidateResultsNode,
)
from src.agents.query.state import QueryState
from src.clients.container import Clients


def _should_regenerate_sql(max_retries: int):
    """Conditional edge out of ``validate_results``: retry ``generate_sql`` while a
    validation error remains and retries are left, otherwise move on to synthesis."""

    def _edge(state: dict[str, Any]) -> str:
        if state.get("validation_error") and state.get("iterations", 0) < max_retries:
            return "generate_sql"
        return "synthesize_answer"

    return _edge


def build_query_graph(clients: Clients) -> CompiledStateGraph:
    """Compile the user query LangGraph.

    Node order is unchanged from the original implementation:
    decompose_query -> retrieve_context -> generate_sql -> execute_sql -> validate_results
    -> (conditional: back to generate_sql while retries remain, else) synthesize_answer
    -> recommend_visualizations
    """
    workflow = StateGraph(QueryState)

    workflow.add_node("decompose_query", DecomposeQueryNode(clients))
    workflow.add_node("retrieve_context", RetrieveContextNode(clients))
    workflow.add_node("generate_sql", GenerateSqlNode(clients))
    workflow.add_node("execute_sql", ExecuteSqlNode(clients))
    workflow.add_node("validate_results", ValidateResultsNode(clients))
    workflow.add_node("synthesize_answer", SynthesizeAnswerNode(clients))
    workflow.add_node("recommend_visualizations", RecommendVisualizationsNode(clients))

    workflow.add_edge(START, "decompose_query")
    workflow.add_edge("decompose_query", "retrieve_context")
    workflow.add_edge("retrieve_context", "generate_sql")
    workflow.add_edge("generate_sql", "execute_sql")
    workflow.add_edge("execute_sql", "validate_results")

    workflow.add_conditional_edges(
        "validate_results",
        _should_regenerate_sql(clients.settings.MAX_SQL_RETRIES),
        {"generate_sql": "generate_sql", "synthesize_answer": "synthesize_answer"},
    )

    workflow.add_edge("synthesize_answer", "recommend_visualizations")
    workflow.add_edge("recommend_visualizations", END)

    return workflow.compile()

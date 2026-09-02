"""Shared state for the user-query LangGraph.

Same keys as the old ``app.agents.user_query.QueryState`` -- every node in this
package is written against exactly this shape, and the API layer builds the initial
dict and reads the final one using these same keys.
"""

from typing import Any, NotRequired, TypedDict


class QueryState(TypedDict):
    question: str
    database_id: str | None
    database_name: str | None
    relevant_context: dict[str, Any]
    generated_sql: str | None
    query_results: list[dict[str, Any]] | None
    validation_error: str | None
    synthesized_answer: str | None
    recommended_visualizations: dict[str, Any] | None
    iterations: int
    sub_questions: list[str] | None
    #: Set by ``BaseNode.failure`` on an unhandled exception; absent otherwise.
    status: NotRequired[str]
    errors: NotRequired[list[str]]

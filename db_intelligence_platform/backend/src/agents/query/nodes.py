"""User-query LangGraph nodes.

One ``BaseNode`` subclass per node in the old ``app/agents/user_query.py`` workflow, in
the same order. Every LLM-calling node preserves its documented exception fallback:
``LLMResponseError`` (a reply that failed schema validation) is caught locally and turns
into that fallback; anything else propagates to ``BaseNode.__call__``, which is a
genuine behaviour change from the old bare ``except Exception`` -- deliberate, so an
actual bug or outage surfaces as a failed run instead of being silently masked.
``synthesize_answer`` and ``execute_sql`` are the two exceptions: they preserve the old
code's broad exception handling exactly, because that is how the retry loop and the
user-facing error message are produced.
"""

from typing import Any

from sqlalchemy import text

from src.agents.base import BaseNode
from src.agents.query.context_retriever import ContextRetriever
from src.agents.query.schemas import SqlPlan, SubQuestions, VisualizationSpec
from src.clients.container import Clients
from src.utils.helpers import LLMResponseError, json_dumps, load_prompt, truncate

NO_CONTEXT_ERROR = "I could not find the relevant details or tables to answer this question."
ORA_ERROR_ANSWER = "I could not find the data you were looking for. Please ask again with more details."
SAMPLE_ROW_LIMIT = 50
RESULT_ROW_LIMIT = 100


class DecomposeQueryNode(BaseNode):
    """Uses LLM to decompose a complex business question into simpler atomic sub-questions."""

    agent = "query"
    name = "decompose_query"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        question = state["question"]
        prompt = load_prompt(self.agent, "decompose_query", question=question)
        try:
            plan = await self.clients.llm.complete_model(prompt, SubQuestions)
            sub_questions = plan.sub_questions
        except LLMResponseError as exc:
            self.log.warning("Decomposition failed, falling back to the raw question: %s", exc)
            sub_questions = [question]
        return {"sub_questions": sub_questions, "iterations": state.get("iterations", 0)}


class RetrieveContextNode(BaseNode):
    """Retrieves relevant schema and entities via Elasticsearch and Neo4j."""

    agent = "query"
    name = "retrieve_context"

    def __init__(self, clients: Clients) -> None:
        super().__init__(clients)
        self._context = ContextRetriever(clients)

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        sub_questions = state.get("sub_questions") or [state["question"]]
        context = dict(state.get("relevant_context") or {})
        context["tables"] = []
        context["relationships"] = []

        try:
            entity_ids = await self._context.match_entities(sub_questions)
            schemas = await self._context.resolve(state.get("database_id"), entity_ids)
        except Exception as exc:
            # Matches the old node's bare ``except Exception`` -- a retrieval failure
            # degrades to "no schema context found" rather than failing the request.
            self.log.warning("Context retrieval failed, proceeding without schema context: %s", exc)
            return {"relevant_context": context}

        if schemas:
            context["available_databases"] = [s.model_dump() for s in schemas]
            context["relationships"] = [{"source": "Entity", "target": "Table", "type": "MAPS_TO"}]
        return {"relevant_context": context}


class GenerateSqlNode(BaseNode):
    """Uses LLM with the retrieved context to generate optimized SQL."""

    agent = "query"
    name = "generate_sql"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        available = state.get("relevant_context", {}).get("available_databases", [])
        if not available:
            return {"validation_error": NO_CONTEXT_ERROR}

        prompt = load_prompt(
            self.agent,
            "generate_sql",
            context_str=json_dumps(available),
            question=state["question"],
        )
        try:
            plan = await self.clients.llm.complete_model(prompt, SqlPlan)
        except LLMResponseError as exc:
            self.log.warning("SQL generation failed: %s", exc)
            return {"validation_error": NO_CONTEXT_ERROR}

        target_name = next(
            (db.get("database_name", plan.target_database_id) for db in available if db.get("database_id") == plan.target_database_id),
            "",
        )
        return {
            "generated_sql": plan.sql,
            "database_id": plan.target_database_id,
            "database_name": target_name,
        }


class ExecuteSqlNode(BaseNode):
    """Executes the generated SQL against the target database."""

    agent = "query"
    name = "execute_sql"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        sql = state.get("generated_sql")
        if not sql:
            return {"validation_error": state.get("validation_error", "No SQL generated to execute.")}

        available = state.get("relevant_context", {}).get("available_databases", [])
        conn_str = next(
            (db.get("conn_str") for db in available if db.get("database_id") == state.get("database_id")),
            None,
        )
        if not conn_str:
            return {"validation_error": "The targeted database connection string could not be found."}

        try:
            async with self.clients.oracle.connect(conn_str) as conn:
                result = await conn.execute(text(sql))
                rows = [dict(mapping) for mapping in result.mappings()]
        except Exception as exc:
            # Captured into validation_error (not status=error) so the retry loop --
            # should_regenerate_sql -- can send this back through generate_sql.
            return {"query_results": None, "validation_error": str(exc)}

        return {"query_results": rows, "validation_error": None}


class ValidateResultsNode(BaseNode):
    """Checks if the execution had errors to decide whether to fix the SQL or proceed."""

    agent = "query"
    name = "validate_results"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        return {"iterations": state.get("iterations", 0) + 1}


class SynthesizeAnswerNode(BaseNode):
    """Takes the question and the raw query results and generates a natural language answer."""

    agent = "query"
    name = "synthesize_answer"
    # Must still run when an earlier node failed unexpectedly, so the user gets a
    # message instead of silence.
    skip_on_error = False

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        validation_error = state.get("validation_error")
        if validation_error:
            return {"synthesized_answer": self._error_answer(validation_error)}

        results = truncate(state.get("query_results"), RESULT_ROW_LIMIT)
        prompt = load_prompt(
            self.agent, "synthesize_answer", question=state["question"], results_str=json_dumps(results)
        )
        try:
            answer = await self.clients.llm.complete_text(prompt)
        except Exception:
            # MOCK FALLBACK preserved from the old node -- any completion failure
            # (not just a schema-validation one; there is no schema here) degrades to
            # a generic row-count summary rather than failing the request.
            self.log.exception("Answer synthesis failed, falling back to a generic summary")
            count = len(state.get("query_results") or [])
            return {"synthesized_answer": f"Based on the extracted database rows, I found {count} records that match your request."}
        return {"synthesized_answer": answer}

    def _error_answer(self, validation_error: str) -> str:
        if "ORA-" in validation_error:
            return ORA_ERROR_ANSWER
        return f"I encountered an error trying to query the database: {validation_error}"


class RecommendVisualizationsNode(BaseNode):
    """LLM determines the best chart type and JSON spec for the frontend ECharts."""

    agent = "query"
    name = "recommend_visualizations"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        query_results = state.get("query_results") or []
        if not query_results:
            return {"recommended_visualizations": None}

        sample = truncate(query_results, SAMPLE_ROW_LIMIT)
        prompt = load_prompt(self.agent, "recommend_visualizations", sample_data=json_dumps(sample))
        try:
            plan = await self.clients.llm.complete_model(prompt, VisualizationSpec)
        except LLMResponseError as exc:
            self.log.warning("Visualization recommendation failed: %s", exc)
            return {"recommended_visualizations": None}

        if plan.is_visualizable and plan.spec:
            return {"recommended_visualizations": {"type": "bar", "spec": plan.spec}}
        return {"recommended_visualizations": None}

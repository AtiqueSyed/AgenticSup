"""Pydantic models validating every LLM reply in the query agent.

These are the typed boundary ``LLMClient.complete_model`` parses replies into (see
``src/utils/helpers.py::parse_llm_json``). A reply that fails validation here becomes an
``LLMResponseError``, which the calling node catches to apply its documented fallback.
"""

from typing import Any

from pydantic import Field, field_validator, model_validator

from src.schemas.base import LenientModel
from src.utils.helpers import strip_code_fences


class SubQuestions(LenientModel):
    """Output of the decompose_query node."""

    sub_questions: list[str] = Field(min_length=1)


class SqlPlan(LenientModel):
    """Output of the generate_sql node."""

    target_database_id: str = ""
    sql: str = Field(min_length=1)

    @field_validator("sql")
    @classmethod
    def _strip_fences(cls, value: str) -> str:
        """Replaces the old manual ```sql / ``` stripping."""
        return strip_code_fences(value)


class VisualizationSpec(LenientModel):
    """Output of the recommend_visualizations node."""

    is_visualizable: bool
    spec: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _require_spec_when_visualizable(self) -> "VisualizationSpec":
        if self.is_visualizable and not self.spec:
            raise ValueError("spec is required when is_visualizable is true")
        return self

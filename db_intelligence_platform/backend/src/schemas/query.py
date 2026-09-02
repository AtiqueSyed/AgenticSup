"""Request/response models for ``/api/v1/query``."""

from typing import Any

from pydantic import Field

from src.schemas.base import ApiModel, StrictModel


class QueryRequest(StrictModel):
    database_id: str | None = None
    question: str = Field(min_length=1, max_length=2000)


class QueryResponse(ApiModel):
    database_id: str | None = None
    database_name: str | None = None
    answer: str
    sql_used: str | None = None
    visualizations: dict[str, Any] | None = None
    results: list[dict[str, Any]] | None = None

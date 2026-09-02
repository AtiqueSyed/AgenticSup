"""Response models for ``/api/v1/stats``."""

from src.schemas.base import ApiModel


class DatabaseSummary(ApiModel):
    id: str
    name: str
    status: str


class StatsResponse(ApiModel):
    total_databases: int
    database_names: list[str]
    databases: list[DatabaseSummary]
    entities_identified: int
    queries_today: int

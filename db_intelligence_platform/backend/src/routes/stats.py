"""``GET /api/v1/stats``."""

from fastapi import APIRouter, Depends

from src.clients.container import Clients, get_clients
from src.core.logging import get_logger
from src.schemas.stats import DatabaseSummary, StatsResponse
from src.services.graph_read import GraphReadService
from src.services.registry_service import DatabaseRegistry

logger = get_logger(__name__)

router = APIRouter()


async def _count_entities(clients: Clients) -> int:
    """Never let a Neo4j hiccup take down the stats endpoint."""
    try:
        return await GraphReadService(clients).count_entities()
    except Exception:
        logger.exception("Failed to count entities for /stats")
        return 0


@router.get("/stats", response_model=StatsResponse)
async def get_stats(clients: Clients = Depends(get_clients)) -> StatsResponse:
    entries = DatabaseRegistry(clients.settings.REGISTRY_PATH).all()
    database_names = [info.get("name", "Unknown DB") for info in entries.values()]
    databases = [
        DatabaseSummary(
            id=db_id,
            name=info.get("name", "Unknown DB"),
            status=info.get("status", "completed"),
        )
        for db_id, info in entries.items()
    ]

    return StatsResponse(
        total_databases=len(database_names),
        database_names=database_names,
        databases=databases,
        entities_identified=await _count_entities(clients),
        queries_today=0,
    )

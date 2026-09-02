"""``/api/v1/onboard*`` -- kicks off and tracks the admin onboarding workflow."""

from fastapi import APIRouter, BackgroundTasks, Depends

from src.clients.container import Clients, get_clients
from src.core.logging import get_logger
from src.schemas.onboarding import (
    DeleteDatabaseResponse,
    OnboardAcceptedResponse,
    OnboardRequest,
    OnboardStatusResponse,
)
from src.services.graph_write import GraphWriteService
from src.services.onboarding_service import OnboardingService
from src.services.registry_service import DatabaseRegistry
from src.services.search_service import SearchService

logger = get_logger(__name__)

router = APIRouter()


@router.post("/onboard", response_model=OnboardAcceptedResponse)
async def onboard_database(
    request: OnboardRequest,
    background_tasks: BackgroundTasks,
    clients: Clients = Depends(get_clients),
) -> OnboardAcceptedResponse:
    """Kicks off the offline Admin Onboarding workflow using LangGraph.

    This will introspect the schema, build the Neo4j graph, and generate embeddings.
    """
    service = OnboardingService(clients)
    db_id = await service.start(request.database_name, request.connection_string)
    background_tasks.add_task(
        service.run, db_id, request.database_name, request.connection_string
    )
    return OnboardAcceptedResponse(message="Onboarding started", database_id=db_id)


@router.delete("/onboard/{database_id}", response_model=DeleteDatabaseResponse)
async def delete_database(
    database_id: str, clients: Clients = Depends(get_clients)
) -> DeleteDatabaseResponse:
    """Removes a database and its full trace from the Knowledge Graph."""
    try:
        await GraphWriteService(clients).delete_database_footprint(database_id)
    except Exception:
        logger.exception("Failed to delete Neo4j footprint for %s", database_id)
    try:
        await SearchService(clients).delete_database_documents(database_id)
    except Exception:
        logger.exception("Failed to delete search documents for %s", database_id)

    DatabaseRegistry(clients.settings.REGISTRY_PATH).remove(database_id)
    return DeleteDatabaseResponse(status="deleted", database_id=database_id)


@router.get("/onboard/{database_id}/status", response_model=OnboardStatusResponse)
async def get_onboarding_status(
    database_id: str, clients: Clients = Depends(get_clients)
) -> OnboardStatusResponse:
    status = DatabaseRegistry(clients.settings.REGISTRY_PATH).get_status(database_id)
    return OnboardStatusResponse(database_id=database_id, status=status or "unknown")

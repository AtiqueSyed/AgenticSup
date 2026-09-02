"""``POST /api/v1/query``."""

from fastapi import APIRouter, Depends, HTTPException

from src.clients.container import Clients, get_clients
from src.core.logging import get_logger
from src.schemas.query import QueryRequest, QueryResponse
from src.services.query_service import QueryService

logger = get_logger(__name__)

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def ask_question(
    request: QueryRequest, clients: Clients = Depends(get_clients)
) -> QueryResponse:
    """Executes the User Query workflow: NL -> SQL -> Validate -> Synthesize Answer."""
    try:
        return await QueryService(clients).ask(request.database_id, request.question)
    except Exception as exc:
        logger.exception("Query failed for database_id=%s", request.database_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

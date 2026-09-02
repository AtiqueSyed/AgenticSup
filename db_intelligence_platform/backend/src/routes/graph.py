"""``/api/v1/graph*`` -- knowledge-graph read and the manual graph-editor mutations."""

from fastapi import APIRouter, Depends, HTTPException

from src.clients.container import Clients, get_clients
from src.core.logging import get_logger
from src.schemas.graph import (
    CreateEdgeRequest,
    CreateNodeRequest,
    GraphResponse,
    MutationResponse,
)
from src.services.graph_read import GraphReadService
from src.services.graph_write import GraphWriteService
from src.services.registry_service import DatabaseRegistry
from src.services.search_service import SearchService

logger = get_logger(__name__)

router = APIRouter()


def _writer(clients: Clients) -> GraphWriteService:
    """Graph-editor mutations require a live Neo4j; the old routes returned a 500 here
    rather than reporting a success that never happened."""
    if not clients.neo4j:
        raise HTTPException(status_code=500, detail="Neo4j not connected")
    return GraphWriteService(clients)


@router.get("/graph", response_model=GraphResponse)
async def get_knowledge_graph(
    database_id: str | None = None, clients: Clients = Depends(get_clients)
) -> GraphResponse:
    """Returns the Neo4j nodes and edges for the frontend visualization.

    If ``database_id`` is provided, only returns the nodes and relationships scoped to
    that specific onboarded database.
    """
    data = await GraphReadService(clients).graph_nodes_and_edges(database_id)
    return GraphResponse(**data)


@router.delete("/graph/clear", response_model=MutationResponse, response_model_exclude_none=True)
async def clear_knowledge_graph(clients: Clients = Depends(get_clients)) -> MutationResponse:
    """Nuclear option to drop all entities and databases from Neo4j and search."""
    try:
        await GraphWriteService(clients).clear_all()
    except Exception:
        logger.exception("Failed to clear the Neo4j graph")
    try:
        await SearchService(clients).clear_entities()
    except Exception:
        logger.exception("Failed to clear the entity search index")

    DatabaseRegistry(clients.settings.REGISTRY_PATH).clear()
    return MutationResponse(status="graph cleared")


@router.post("/graph/node", response_model=MutationResponse, response_model_exclude_none=True)
async def create_custom_node(
    request: CreateNodeRequest, clients: Clients = Depends(get_clients)
) -> MutationResponse:
    await _writer(clients).upsert_node(
        request.id, request.name, request.type, request.description
    )
    return MutationResponse(status="created", node_id=request.id)


@router.post("/graph/edge", response_model=MutationResponse, response_model_exclude_none=True)
async def create_custom_edge(
    request: CreateEdgeRequest, clients: Clients = Depends(get_clients)
) -> MutationResponse:
    created = await _writer(clients).upsert_edge(request.source, request.target, request.type)
    if not created:
        # Both endpoints are MATCHed, so an unknown id writes nothing at all. Saying
        # "created" here would leave the editor drawing an edge Neo4j does not have.
        raise HTTPException(
            status_code=404, detail="source and target must both be existing nodes"
        )
    return MutationResponse(status="created", source=request.source, target=request.target)


@router.delete("/graph/node/{node_id}", response_model=MutationResponse, response_model_exclude_none=True)
async def delete_custom_node(
    node_id: str, clients: Clients = Depends(get_clients)
) -> MutationResponse:
    await _writer(clients).delete_node(node_id)
    return MutationResponse(status="deleted", node_id=node_id)


@router.delete("/graph/edge/{source_id}/{target_id}/{edge_type}", response_model=MutationResponse, response_model_exclude_none=True)
async def delete_custom_edge(
    source_id: str, target_id: str, edge_type: str, clients: Clients = Depends(get_clients)
) -> MutationResponse:
    await _writer(clients).delete_edge(source_id, target_id, edge_type)
    return MutationResponse(status="deleted")

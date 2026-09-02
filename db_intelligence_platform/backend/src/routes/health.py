"""``GET /health`` -- mounted at the root, outside ``/api/v1``, per the frozen contract."""

from fastapi import APIRouter, Depends

from src.core.config import Settings, get_settings

router = APIRouter()


@router.get("/health", response_model=dict[str, str])
async def health_check(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {
        "status": "ok",
        "llm_provider": settings.OPENAI_BASE_URL,
        "oracle_host": settings.ORACLE_HOST,
        "neo4j_uri": settings.NEO4J_URI,
    }

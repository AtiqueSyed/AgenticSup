"""Router aggregation.

``main.py`` imports exactly these two names. ``health_router`` is mounted at the root
and ``api_router`` under ``/api/v1``, matching the frozen contract.
"""

from fastapi import APIRouter

from src.routes import graph, health, onboarding, query, stats

api_router = APIRouter()
health_router = APIRouter()

health_router.include_router(health.router)
api_router.include_router(stats.router)
api_router.include_router(onboarding.router)
api_router.include_router(query.router)
api_router.include_router(graph.router)

__all__ = ["api_router", "health_router"]

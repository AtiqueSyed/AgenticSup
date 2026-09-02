"""Application factory.

``create_app`` exists so tests can build an isolated instance with overridden
dependencies instead of importing a module-level singleton that has already opened
network connections.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import Settings, get_settings
from src.core.lifespan import lifespan
from src.core.logging import setup_logging
from src.core.telemetry import setup_telemetry
from src.routes import api_router, health_router

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.LOG_LEVEL)

    app = FastAPI(
        title="Enterprise Agentic Database Intelligence Platform API",
        description=(
            "Backend API for managing databases, executing natural language queries, "
            "and interacting with the knowledge graph."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Update this in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    setup_telemetry(app, settings)
    # /health stays at the root; everything else is versioned. Both paths are part of
    # the frozen contract the frontend depends on.
    app.include_router(health_router)
    app.include_router(api_router, prefix=API_PREFIX)
    return app


app = create_app()

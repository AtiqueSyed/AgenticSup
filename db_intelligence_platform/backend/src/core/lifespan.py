"""Application lifespan: build clients on startup, close them on shutdown."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.clients.container import Clients, set_clients
from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Starting %s", settings.OTEL_SERVICE_NAME)

    clients = Clients.build(settings)
    set_clients(clients)
    clients.embeddings.warm_up()

    try:
        yield
    finally:
        logger.info("Shutting down; closing clients")
        await clients.close()
        set_clients(None)

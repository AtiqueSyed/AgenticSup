"""Oracle engine construction.

Engines are created per target database (each onboarded DB has its own connection
string), so this is a factory rather than a long-lived client. SQLAlchemy itself is
auto-instrumented by OTel, so no manual spans are needed here.
"""

import urllib.parse
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.core.config import Settings
from src.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_CONNECT_TIMEOUT = 5


def build_oracle_url(settings: Settings) -> str:
    """DSN for the platform's own metadata database.

    Username and password are URL-encoded: the deployed accounts contain ``#``, which
    silently truncates the DSN otherwise.
    """
    user = urllib.parse.quote_plus(settings.ORACLE_USERNAME)
    password = urllib.parse.quote_plus(settings.ORACLE_PASSWORD.get_secret_value())
    dsn = f"{settings.ORACLE_HOST}:{settings.ORACLE_PORT}/{settings.ORACLE_SERVICE_NAME}"
    return f"oracle+oracledb_async://{user}:{password}@{dsn}"


class OracleEngineFactory:
    """Creates short-lived async engines for arbitrary connection strings."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def platform_url(self) -> str:
        return build_oracle_url(self._settings)

    def create(self, connection_string: str, **kwargs: Any) -> AsyncEngine:
        return create_async_engine(connection_string, **kwargs)

    @asynccontextmanager
    async def connect(self, connection_string: str, *, timeout: int = DEFAULT_CONNECT_TIMEOUT):
        """Connection scoped to a ``with`` block; the engine is always disposed."""
        engine = self.create(connection_string, connect_args={"timeout": timeout})
        try:
            async with engine.connect() as connection:
                yield connection
        finally:
            await engine.dispose()

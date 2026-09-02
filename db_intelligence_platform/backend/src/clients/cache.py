"""Hazelcast-backed cache, used for chat session history.

The API is JSON in / JSON out because every current caller stores serialised history.
Failures are logged and swallowed on purpose: a cache miss must never fail a user query.
"""

import json
from typing import Any

import hazelcast

from src.core.config import Settings
from src.core.logging import get_logger
from src.core.telemetry import get_tracer

logger = get_logger(__name__)
tracer = get_tracer(__name__)


class CacheClient:
    def __init__(self, client: Any) -> None:
        self._client = client

    @classmethod
    def create(cls, settings: Settings) -> "CacheClient | None":
        try:
            client = hazelcast.HazelcastClient(
                cluster_name=settings.HAZELCAST_CLUSTER_NAME,
                cluster_members=[f"{settings.HAZELCAST_HOST}:{settings.HAZELCAST_PORT}"],
                cluster_connect_timeout=2.0,
            )
        except Exception:
            logger.exception("Failed to initialise Hazelcast client")
            return None
        return cls(client)

    def get_json(self, map_name: str, key: str, default: Any = None) -> Any:
        with tracer.start_as_current_span("cache.get", attributes={"cache.map": map_name}):
            try:
                raw = self._client.get_map(map_name).blocking().get(key)
                return json.loads(raw) if raw else default
            except Exception:
                logger.exception("Cache read failed for %s/%s", map_name, key)
                return default

    def put_json(self, map_name: str, key: str, value: Any) -> None:
        with tracer.start_as_current_span("cache.put", attributes={"cache.map": map_name}):
            try:
                self._client.get_map(map_name).blocking().put(key, json.dumps(value))
            except Exception:
                logger.exception("Cache write failed for %s/%s", map_name, key)

    def close(self) -> None:
        self._client.shutdown()

"""Elasticsearch client wrapper.

The transport is auto-instrumented by OTel, so this class exists for the narrower
purpose of giving services a small, typed surface instead of raw ES call signatures --
and of turning "index missing" into a normal, logged outcome rather than an exception.
"""

from typing import Any

from elasticsearch import AsyncElasticsearch

from src.core.config import Settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class ElasticClient:
    def __init__(self, client: AsyncElasticsearch) -> None:
        self._client = client

    @classmethod
    def create(cls, settings: Settings) -> "ElasticClient | None":
        try:
            client = AsyncElasticsearch(
                settings.ELASTICSEARCH_URL,
                basic_auth=(
                    settings.ELASTICSEARCH_USERNAME,
                    settings.ELASTICSEARCH_PASSWORD.get_secret_value(),
                ),
                verify_certs=False,
            )
        except Exception:
            logger.exception("Failed to initialise Elasticsearch client")
            return None
        return cls(client)

    async def index_exists(self, index: str) -> bool:
        return bool(await self._client.indices.exists(index=index))

    async def create_index(self, index: str, mapping: dict[str, Any]) -> None:
        await self._client.indices.create(index=index, body=mapping)

    async def index_document(self, index: str, doc_id: str, document: dict[str, Any]) -> None:
        await self._client.index(index=index, id=doc_id, document=document)

    async def knn_search(self, index: str, body: dict[str, Any]) -> list[dict[str, Any]]:
        """Returns the raw hit list; an absent index yields no hits rather than an error."""
        if not await self.index_exists(index):
            logger.info("Index %s does not exist yet", index)
            return []
        response = await self._client.search(index=index, body=body)
        return response.get("hits", {}).get("hits", [])

    async def delete_by_query(self, index: str, query: dict[str, Any]) -> None:
        await self._client.delete_by_query(index=index, query=query, ignore_unavailable=True)

    async def close(self) -> None:
        await self._client.close()

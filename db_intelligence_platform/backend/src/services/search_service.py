"""Elasticsearch-backed entity search.

Ported from ``admin_onboarding.py``'s ``generate_embeddings_node`` (index mapping and
document shape) and ``user_query.py``'s ``retrieve_context_node`` (the per-question kNN
lookup). Owns the entity index mapping, the kNN lookup used during retrieval, and the
per-database cleanup the onboarding and delete routes call.
"""

from src.clients.container import Clients
from src.core.logging import get_logger
from src.schemas.domain import EntityRecord

logger = get_logger(__name__)

KNN_CANDIDATES = 50


class SearchService:
    def __init__(self, clients: Clients) -> None:
        self.clients = clients
        self.elastic = clients.elastic
        self.embeddings = clients.embeddings
        self.settings = clients.settings

    async def ensure_entity_index(self) -> None:
        """Create the entities index with its ``dense_vector`` mapping if absent.

        Dimensions come from ``settings.EMBEDDING_DIMENSIONS`` so the mapping and the
        embedding model can never drift apart.
        """
        if not self.elastic:
            return
        index = self.settings.entities_index()
        if await self.elastic.index_exists(index):
            return
        mapping = {
            "mappings": {
                "properties": {
                    "database_id": {"type": "keyword"},
                    "entity_id": {"type": "keyword"},
                    "description": {"type": "text"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": self.settings.EMBEDDING_DIMENSIONS,
                        "index": True,
                        "similarity": "cosine",
                    },
                }
            }
        }
        await self.elastic.create_index(index, mapping)

    async def index_entities(self, database_id: str, entities: list[EntityRecord]) -> int:
        """Embed and index each entity. Returns how many were indexed.

        The embedding text is the entity id itself (e.g. "Bank", "Complaint") -- matching
        the old onboarding node so retrieval, which embeds natural-language questions
        against the same space, keeps working.
        """
        if not self.elastic or not entities:
            return 0
        await self.ensure_entity_index()
        index = self.settings.entities_index()
        for entity in entities:
            embedding = self.embeddings.embed(entity.id)
            await self.elastic.index_document(
                index,
                entity.id,
                {
                    "database_id": database_id,
                    "entity_id": entity.id,
                    "description": entity.description,
                    "embedding": embedding,
                },
            )
        return len(entities)

    async def match_entity_ids(self, questions: list[str], top_k: int = 1) -> list[str]:
        """kNN search per question, de-duplicated in first-seen order.

        Order matters: the retrieval step feeds these ids straight into Cypher. A
        failure on one question is logged and skipped rather than aborting the rest.
        """
        if not self.elastic:
            return []
        index = self.settings.entities_index()
        matched: list[str] = []
        for question in questions:
            try:
                await self._match_one(index, question, top_k, matched)
            except Exception:
                logger.exception("Entity match failed for sub-question %r", question[:80])
        return matched

    async def _match_one(self, index: str, question: str, top_k: int, matched: list[str]) -> None:
        vector = self.embeddings.embed(question)
        body = {
            "knn": {
                "field": "embedding",
                "query_vector": vector,
                "k": top_k,
                "num_candidates": KNN_CANDIDATES,
            }
        }
        hits = await self.elastic.knn_search(index, body)
        for hit in hits[:top_k]:
            entity_id = hit.get("_source", {}).get("entity_id")
            if entity_id and entity_id not in matched:
                matched.append(entity_id)

    async def delete_database_documents(self, database_id: str) -> None:
        """Remove this database's entity and table documents from both indices."""
        if not self.elastic:
            return
        await self.elastic.delete_by_query(self.settings.entities_index(), {"term": {"database_id": database_id}})
        await self.elastic.delete_by_query(self.settings.tables_index(), {"term": {"database_id": database_id}})

    async def clear_entities(self) -> None:
        """Drop every entity document. Backs ``DELETE /graph/clear``."""
        if not self.elastic:
            return
        await self.elastic.delete_by_query(self.settings.entities_index(), {"match_all": {}})

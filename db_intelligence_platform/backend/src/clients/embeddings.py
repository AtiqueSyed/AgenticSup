"""Embedding client.

The old code called ``TextEmbedding("BAAI/bge-small-en-v1.5")`` inside two hot paths --
once per ``/query`` request and once per onboarding run -- reloading the model from disk
every single time. Here the model is built once and reused, which is the largest
latency win available in this codebase.
"""

from fastembed import TextEmbedding

from src.core.config import Settings
from src.core.logging import get_logger
from src.core.telemetry import get_tracer

logger = get_logger(__name__)
tracer = get_tracer(__name__)


class EmbeddingClient:
    """Wraps a single lazily-built ``TextEmbedding`` instance."""

    def __init__(self, settings: Settings) -> None:
        self._model_name = settings.EMBEDDING_MODEL
        self._dimensions = settings.EMBEDDING_DIMENSIONS
        self._model: TextEmbedding | None = None

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def _ensure_model(self) -> TextEmbedding:
        """Built on first use so importing the app never downloads a model."""
        if self._model is None:
            logger.info("Loading embedding model %s", self._model_name)
            self._model = TextEmbedding(model_name=self._model_name)
        return self._model

    def embed(self, text: str) -> list[float]:
        """Vector for one string. Returns a zero-ish vector if the model fails, so a
        single bad input degrades one search instead of failing the request."""
        with tracer.start_as_current_span(
            "embeddings.embed", attributes={"embedding.model": self._model_name}
        ):
            try:
                return list(next(iter(self._ensure_model().embed([text]))))
            except Exception:
                logger.exception("Embedding failed for %r", text[:80])
                return [0.001] * self._dimensions

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]

    def warm_up(self) -> None:
        """Called at startup so the first user request does not pay the load cost."""
        self._ensure_model()

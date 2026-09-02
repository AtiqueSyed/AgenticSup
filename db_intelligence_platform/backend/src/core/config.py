"""Application settings.

Every value the app needs comes from here, validated once at startup. Secrets are
``SecretStr`` so they cannot leak into a log line, a traceback, or a span attribute
by accident -- ``repr`` of a ``SecretStr`` is ``**********``.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- LLM ---
    OPENAI_API_KEY: SecretStr
    OPENAI_BASE_URL: str
    OPENAI_PROJECT_ID: str = ""
    DEFAULT_LLM_MODEL: str

    # --- Neo4j ---
    NEO4J_URI: str
    NEO4J_USERNAME: str
    NEO4J_PASSWORD: SecretStr

    # --- Hazelcast ---
    HAZELCAST_HOST: str
    HAZELCAST_PORT: int = Field(ge=1, le=65535)
    HAZELCAST_CLUSTER_NAME: str

    # --- Elasticsearch ---
    ELASTICSEARCH_URL: str
    ELASTICSEARCH_USERNAME: str
    ELASTICSEARCH_PASSWORD: SecretStr
    ELASTICSEARCH_INDEX_PREFIX: str

    # --- Oracle ---
    ORACLE_HOST: str
    ORACLE_PORT: int = Field(ge=1, le=65535)
    ORACLE_SERVICE_NAME: str
    ORACLE_USERNAME: str
    ORACLE_PASSWORD: SecretStr

    # --- Application ---
    REGISTRY_PATH: str = "registry.json"
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSIONS: int = 384
    MAX_SQL_RETRIES: int = Field(default=3, ge=1, le=10)
    LOG_LEVEL: str = "INFO"

    # --- OpenTelemetry ---
    # OTEL_* names follow the OTel environment-variable spec so standard tooling
    # and auto-instrumentation agents pick them up unchanged.
    OTEL_SERVICE_NAME: str = "db-intelligence-backend"
    OTEL_SDK_DISABLED: bool = False
    OTEL_TRACES_EXPORTER: Literal["otlp", "console", "none"] = "otlp"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_CAPTURE_CONTENT: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("NEO4J_URI")
    @classmethod
    def _validate_neo4j_uri(cls, value: str) -> str:
        allowed = ("neo4j://", "neo4j+s://", "neo4j+ssc://", "bolt://", "bolt+s://")
        if not value.startswith(allowed):
            raise ValueError(f"NEO4J_URI must start with one of {allowed}")
        return value

    @field_validator("OPENAI_BASE_URL", "ELASTICSEARCH_URL")
    @classmethod
    def _validate_http_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return value

    @field_validator("LOG_LEVEL")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        level = value.upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"Unsupported LOG_LEVEL: {value}")
        return level

    def entities_index(self) -> str:
        """Elasticsearch index holding entity embeddings."""
        return f"{self.ELASTICSEARCH_INDEX_PREFIX}entities"

    def tables_index(self) -> str:
        """Elasticsearch index holding table semantic descriptions."""
        return f"{self.ELASTICSEARCH_INDEX_PREFIX}tables"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached accessor -- the single place a ``Settings`` instance is built."""
    return Settings()

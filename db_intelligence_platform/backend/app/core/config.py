from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # LLM Configuration
    OPENAI_API_KEY: str
    OPENAI_BASE_URL: str
    OPENAI_PROJECT_ID: str
    DEFAULT_LLM_MODEL: str

    # Neo4j
    NEO4J_URI: str
    NEO4J_USERNAME: str
    NEO4J_PASSWORD: str

    # Hazelcast
    HAZELCAST_HOST: str
    HAZELCAST_PORT: int
    HAZELCAST_CLUSTER_NAME: str

    # Elasticsearch
    ELASTICSEARCH_URL: str
    ELASTICSEARCH_USERNAME: str
    ELASTICSEARCH_PASSWORD: str
    ELASTICSEARCH_INDEX_PREFIX: str

    # Oracle DB
    ORACLE_HOST: str
    ORACLE_PORT: int
    ORACLE_SERVICE_NAME: str
    ORACLE_USERNAME: str
    ORACLE_PASSWORD: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

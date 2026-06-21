import oracledb
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from neo4j import AsyncGraphDatabase
import hazelcast
from elasticsearch import AsyncElasticsearch
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

import urllib.parse

# --- Oracle DB (SQLAlchemy) ---
# Assuming thin client mode for oracledb
ORACLE_DSN = f"{settings.ORACLE_HOST}:{settings.ORACLE_PORT}/{settings.ORACLE_SERVICE_NAME}"
# URL-encode the username and password to safely handle special characters like '#'
safe_username = urllib.parse.quote_plus(settings.ORACLE_USERNAME)
safe_password = urllib.parse.quote_plus(settings.ORACLE_PASSWORD)
# We're using oracledb async support with SQLAlchemy 2.0
ORACLE_URL = f"oracle+oracledb_async://{safe_username}:{safe_password}@{ORACLE_DSN}"

try:
    engine = create_async_engine(ORACLE_URL, echo=False, connect_args={"timeout": 5})
    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
except Exception as e:
    logger.error(f"Failed to initialize Oracle engine: {e}")
    engine = None
    AsyncSessionLocal = None

async def get_db():
    if not AsyncSessionLocal:
        yield None
        return
    async with AsyncSessionLocal() as session:
        yield session

# --- Neo4j ---
try:
    neo4j_driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD)
    )
except Exception as e:
    logger.error(f"Failed to initialize Neo4j driver: {e}")
    neo4j_driver = None

# --- Hazelcast ---
try:
    hz_client = hazelcast.HazelcastClient(
        cluster_name=settings.HAZELCAST_CLUSTER_NAME,
        cluster_members=[f"{settings.HAZELCAST_HOST}:{settings.HAZELCAST_PORT}"],
        cluster_connect_timeout=2.0
    )
except Exception as e:
    logger.error(f"Failed to initialize Hazelcast client: {e}")
    hz_client = None

# --- Elasticsearch ---
try:
    es_client = AsyncElasticsearch(
        settings.ELASTICSEARCH_URL,
        basic_auth=(settings.ELASTICSEARCH_USERNAME, settings.ELASTICSEARCH_PASSWORD),
        verify_certs=False # Typically false for hackathon environments unless specified
    )
except Exception as e:
    logger.error(f"Failed to initialize Elasticsearch client: {e}")
    es_client = None

async def close_connections():
    """Helper to gracefully close external connections"""
    if neo4j_driver:
        await neo4j_driver.close()
    if es_client:
        await es_client.close()
    if hz_client:
        hz_client.shutdown()

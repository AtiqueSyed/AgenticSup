import asyncio
import sys
import os

# Add the current directory to sys.path so we can import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from sqlalchemy import text

async def test_oracle():
    print("Testing Oracle DB Connection...")
    # Import database here to ensure we print details if it fails during import
    try:
        from app.core.database import engine
    except Exception as e:
        print(f"[FAIL] Failed to import database or initialize Oracle engine: {e}")
        return False
        
    if not engine:
        print("[FAIL] Oracle engine is None.")
        return False
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1 FROM dual"))
            val = result.scalar()
            print(f"[SUCCESS] Oracle DB Connection works! Query result: {val}")
            return True
    except Exception as e:
        print(f"[FAIL] Oracle DB Connection error: {e}")
        return False

async def test_neo4j():
    print("Testing Neo4j Connection...")
    try:
        from app.core.database import neo4j_driver
    except Exception as e:
        print(f"[FAIL] Failed to import neo4j_driver: {e}")
        return False
        
    if not neo4j_driver:
        print("[FAIL] Neo4j driver is None.")
        return False
    try:
        async with neo4j_driver.session() as session:
            result = await session.run("RETURN 1 AS val")
            record = await result.single()
            print(f"[SUCCESS] Neo4j Connection works! Result: {record['val']}")
            return True
    except Exception as e:
        print(f"[FAIL] Neo4j Connection error: {e}")
        return False

async def test_elasticsearch():
    print("Testing Elasticsearch Connection...")
    try:
        from app.core.database import es_client
    except Exception as e:
        print(f"[FAIL] Failed to import es_client: {e}")
        return False
        
    if not es_client:
        print("[FAIL] Elasticsearch client is None.")
        return False
    try:
        info = await es_client.info()
        print(f"[SUCCESS] Elasticsearch Connection works! Cluster info: {info.get('cluster_name')}")
        return True
    except Exception as e:
        print(f"[FAIL] Elasticsearch Connection error: {e}")
        return False

async def main():
    print("Starting connection tests...")
    print(f"Oracle settings: host={settings.ORACLE_HOST}, port={settings.ORACLE_PORT}, service={settings.ORACLE_SERVICE_NAME}, user={settings.ORACLE_USERNAME}")
    
    oracle_ok = await test_oracle()
    neo4j_ok = await test_neo4j()
    es_ok = await test_elasticsearch()
    
    print("\n--- Summary ---")
    print(f"Oracle DB: {'OK' if oracle_ok else 'FAILED'}")
    print(f"Neo4j: {'OK' if neo4j_ok else 'FAILED'}")
    print(f"Elasticsearch: {'OK' if es_ok else 'FAILED'}")
    
    # Clean up connections
    try:
        from app.core.database import close_connections
        await close_connections()
    except Exception as e:
        print(f"Error during close_connections: {e}")

if __name__ == "__main__":
    asyncio.run(main())

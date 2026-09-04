import asyncio
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "db_intelligence_platform/backend"))

from app.core.database import neo4j_driver
import json

async def main():
    if not neo4j_driver:
        print("Neo4j driver not initialized.")
        return
        
    async with neo4j_driver.session() as session:
        res = await session.run("""
            MATCH (db:Database)
            RETURN db.name AS name, db.connection_string AS conn_str
        """)
        records = await res.data()
        
        for r in records:
            print(f"DB: {r['name']}, Conn: {r['conn_str']}")

if __name__ == "__main__":
    asyncio.run(main())

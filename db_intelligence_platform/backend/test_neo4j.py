import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import neo4j_driver

async def main():
    if not neo4j_driver:
        print("Neo4j driver not initialized.")
        return
        
    async with neo4j_driver.session() as session:
        res = await session.run("MATCH (e:Entity) RETURN e.id AS id, e.name AS name")
        records = await res.data()
        print("TOTAL ENTITY NODES:", len(records))
        for r in records:
            print(f"ID: {r['id']} | Name: {r['name']}")

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "db_intelligence_platform/backend"))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test_conn(conn_str):
    print(f"Testing: {conn_str}")
    engine = create_async_engine(conn_str)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT bank_name, COUNT(*) AS total_penalties FROM inspection_reports WHERE observation LIKE '%penalty%' GROUP BY bank_name"))
            print("Success:", [dict(mapping) for mapping in result.mappings()])
    except Exception as e:
        print("Error:", type(e).__name__)
        print(str(e))
    finally:
        await engine.dispose()

async def main():
    conns = [
        "oracle+oracledb_async://C%23%23agenticsupervisor_daksh:agenticsupervisor@host.docker.internal:1521/?service_name=XE",
    ]
    for c in conns:
        await test_conn(c)

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "db_intelligence_platform/backend"))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    conn_str = "oracle+oracledb_async://C%23%23agenticsupervisor_cims:agenticsupervisor@localhost:1521/?service_name=XEPDB1"
    # Using localhost:1521 since host.docker.internal is 1521 inside docker, but mapped to 1521 externally? Wait.
    # In registry.json: "oracle+oracledb_async://C%23%23agenticsupervisor_cims:agenticsupervisor@localhost:1521/?service_name=XEPDB1"
    
    engine = create_async_engine(conn_str)
    try:
        async with engine.connect() as conn:
            sql = """
            SELECT f.lq_bkt_sk, COUNT(*) as deposit_count
            FROM fact_ebr_lna_lq f
            WHERE f.lq_bkt_sk IN (SELECT lq_bkt_sk FROM fact_ebr_borrowings_lq)
            GROUP BY f.lq_bkt_sk
            HAVING COUNT(*) > 1
            ORDER BY deposit_count DESC
            """
            print(f"Executing: {sql}")
            result = await conn.execute(text(sql))
            rows = [dict(mapping) for mapping in result.mappings()]
            print("Results:", rows)
    except Exception as e:
        print("Error:", type(e).__name__)
        print(str(e))
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())

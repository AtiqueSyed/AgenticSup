import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    # Try connecting to the pluggable database XEPDB1
    url = "oracle+oracledb_async://agenticsupervisor_developer:agenticsupervisor@localhost:1522/?service_name=XEPDB1"
    print(f"Testing connection to: {url}")
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1 FROM dual"))
            print(f"[SUCCESS] Connected to XEPDB1! Dual query result: {result.scalar()}")
            
            # Query tables
            tables_res = await conn.execute(text("""
                SELECT owner, table_name 
                FROM all_tables 
                WHERE owner NOT IN ('SYS', 'SYSTEM', 'XDB', 'CTXSYS', 'MDSYS', 'DBSNMP', 'OUTLN', 'APPQOSSYS', 'DVSYS', 'DVF', 'AUDSYS', 'OJVMSYS', 'GSMADMIN_INTERNAL', 'ORDSYS', 'OLAPSYS', 'WMSYS', 'SYSRAC', 'SYSKM', 'SYSDG', 'SYSBACKUP', 'SYS$UMF', 'REMOTE_SCHEDULER_AGENT', 'DIP', 'GSMCATUSER', 'GSMUSER', 'XS$NULL', 'ANONYMOUS', 'FLOWS_FILES')
            """))
            rows = tables_res.fetchall()
            print("Tables in XEPDB1:")
            for r in rows:
                print(f"Owner: {r[0]} | Table: {r[1]}")
    except Exception as e:
        print(f"[FAIL] Connection failed: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())

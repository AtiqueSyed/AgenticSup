import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings

async def main():
    user_escaped = settings.ORACLE_USERNAME.replace("#", "%23")
    url = f"oracle+oracledb_async://{user_escaped}:{settings.ORACLE_PASSWORD}@{settings.ORACLE_HOST}:{settings.ORACLE_PORT}/?service_name={settings.ORACLE_SERVICE_NAME}"
    engine = create_async_engine(url)
    
    async with engine.connect() as conn:
        # Query ALL_TABLES to see all tables visible to the user
        result = await conn.execute(text("""
            SELECT owner, table_name 
            FROM all_tables 
            WHERE owner NOT IN ('SYS', 'SYSTEM', 'XDB', 'CTXSYS', 'MDSYS', 'DBSNMP', 'OUTLN', 'APPQOSSYS', 'DVSYS', 'DVF', 'AUDSYS', 'OJVMSYS', 'GSMADMIN_INTERNAL', 'ORDSYS', 'OLAPSYS', 'WMSYS', 'SYSRAC', 'SYSKM', 'SYSDG', 'SYSBACKUP', 'SYS$UMF', 'REMOTE_SCHEDULER_AGENT', 'DIP', 'GSMCATUSER', 'GSMUSER', 'XS$NULL', 'ANONYMOUS', 'FLOWS_FILES')
            ORDER BY owner, table_name
        """))
        rows = result.fetchall()
        print("Visible User Tables in Database:")
        for r in rows:
            print(f"Owner: {r[0]} | Table: {r[1]}")
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())

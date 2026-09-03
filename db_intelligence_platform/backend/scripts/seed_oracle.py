"""Seed the local demo Oracle instance with the two CMS/DAKSH "databases".

Why this exists: the onboarding demo needs two schemas that look and behave like
separate production databases so the platform's schema-introspection agent has
something real to ingest. CMS and DAKSH are plain PDB-local Oracle users (created by
infra/oracle/init/01_users.sql, no cross-schema grants between them) and this script
creates each user's own tables and loads them from the source CSV/XLSX files in
rbi_nl2sql_agents/project_data/.

Idempotent by design: each table is dropped (if it exists) and recreated before every
load, so re-running this script always ends in the same state. Run with:

    uv run python scripts/seed_oracle.py
"""

import csv
import datetime
import os
import sys
from pathlib import Path
from typing import Any, Callable, NamedTuple

import oracledb
import openpyxl

REPO_ROOT = Path(__file__).resolve().parents[3]
PROJECT_DATA = REPO_ROOT / "rbi_nl2sql_agents" / "project_data"
CMS_DIR = PROJECT_DATA / "cms"
DAKSH_DIR = PROJECT_DATA / "daksh"

BATCH_SIZE = 500
EXCEL_EPOCH = datetime.date(1899, 12, 30)
_MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], start=1
)}


def excel_date(value: Any) -> datetime.date | None:
    """openpyxl already parses date-formatted xlsx cells into datetimes for us, but
    fall back to the classic 1899-12-30 serial epoch if it ever hands back a raw
    number instead (e.g. a cell without date formatting)."""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, (int, float)):
        return EXCEL_EPOCH + datetime.timedelta(days=value)
    return None


def csv_date(value: str) -> datetime.date | None:
    """CSV dates are 'DD-MON-YY' (e.g. '20-DEC-18'). Parsed by hand instead of
    strptime's locale-dependent %b."""
    if not value:
        return None
    day, mon, yr = value.split("-")
    year = int(yr) + (2000 if int(yr) < 70 else 1900)
    return datetime.date(year, _MONTHS[mon.upper()], int(day))


def csv_int(value: str) -> int | None:
    return int(value) if value else None


def csv_str(value: str) -> str | None:
    return value if value else None


def truncate(value: Any, max_len_bytes: int) -> str | None:
    """Most cells here are strings, but a stray free-text cell that looks like a bare
    number (e.g. one FACTS value in cases.xlsx) comes back from openpyxl as an int --
    stringify before slicing. VARCHAR2(n) without a CHAR qualifier caps at n *bytes*,
    and this text has multi-byte characters (e.g. rupee signs), so truncate by encoded
    byte length rather than Python string length, decoding with errors="ignore" in
    case the cut lands mid multi-byte character."""
    if value is None or value == "":
        return None
    encoded = str(value).encode("utf-8")
    if len(encoded) <= max_len_bytes:
        return str(value)
    return encoded[:max_len_bytes].decode("utf-8", errors="ignore")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_xlsx_rows(path: Path) -> list[dict[str, Any]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = next(rows)
    data = [dict(zip(header, row)) for row in rows]
    wb.close()
    return data


class Table(NamedTuple):
    name: str
    ddl: str
    columns: list[str]  # INSERT column order -- also defines the ":n" bind order
    rows_fn: Callable[[], list[tuple]]

    def insert_sql(self) -> str:
        binds = ", ".join(f":{i}" for i in range(1, len(self.columns) + 1))
        return f"INSERT INTO {self.name} ({', '.join(self.columns)}) VALUES ({binds})"


# --------------------------------------------------------------------------- CMS
# REGIONS/QUEUE/QUEUEMEMBERS DDL is reused verbatim from cms/*_schema_info.md, minus
# the CRMNEXT. schema prefix.

REGIONS_DDL = """
CREATE TABLE REGIONS (
    OWNERID NUMBER(10,0) NOT NULL,
    REGIONID NUMBER(10,0) NOT NULL,
    PARENTREGIONID NUMBER(10,0),
    ISPARENT NUMBER(1,0),
    NAME NVARCHAR2(256) NOT NULL,
    DESCRIPTION NVARCHAR2(2000),
    CREATEDBY NUMBER(10,0),
    CREATEDON DATE,
    LASTMODIFIEDBY NUMBER(10,0),
    LASTMODIFIEDON DATE,
    ZIPCODE NVARCHAR2(64),
    CATEGORYTYPE NUMBER(10,0) NOT NULL,
    CONTINENTID NUMBER(10,0),
    CONTINENTNAME NVARCHAR2(256),
    ZONEID NUMBER(10,0),
    ZONENAME NVARCHAR2(256),
    AREAID NUMBER(10,0),
    AREANAME NVARCHAR2(256),
    CLUSTERID NUMBER(10,0),
    CLUSTERNAME NVARCHAR2(256),
    BRANCHID NUMBER(10,0),
    BRANCHNAME NVARCHAR2(256),
    LOCATIONID NUMBER(10,0),
    LOCATIONNAME NVARCHAR2(256),
    PROCESSID NUMBER(10,0) NOT NULL,
    PROCESSVERSION NUMBER(10,0) NOT NULL,
    LAYOUTID NUMBER(10,0) NOT NULL,
    CONSTRAINT PK_REGIONS PRIMARY KEY (REGIONID)
    -- No FK from PARENTREGIONID to REGIONID: 0 marks the four top-level zones and is
    -- not itself a REGIONID, so a self-referencing FK would reject those rows.
)
"""

REGIONS_COLUMNS = [
    "OWNERID", "REGIONID", "PARENTREGIONID", "ISPARENT", "NAME", "DESCRIPTION",
    "CREATEDBY", "CREATEDON", "LASTMODIFIEDBY", "LASTMODIFIEDON", "ZIPCODE",
    "CATEGORYTYPE", "CONTINENTID", "CONTINENTNAME", "ZONEID", "ZONENAME", "AREAID",
    "AREANAME", "CLUSTERID", "CLUSTERNAME", "BRANCHID", "BRANCHNAME", "LOCATIONID",
    "LOCATIONNAME", "PROCESSID", "PROCESSVERSION", "LAYOUTID",
]


def regions_rows() -> list[tuple]:
    return [
        tuple(
            csv_date(r[c]) if c in ("CREATEDON", "LASTMODIFIEDON")
            else csv_str(r[c]) if c in ("NAME", "DESCRIPTION", "ZIPCODE", "CONTINENTNAME",
                                         "ZONENAME", "AREANAME", "CLUSTERNAME", "BRANCHNAME",
                                         "LOCATIONNAME")
            else csv_int(r[c])
            for c in REGIONS_COLUMNS
        )
        for r in read_csv_rows(CMS_DIR / "regions.csv")
    ]


QUEUE_DDL = """
CREATE TABLE QUEUE (
    OWNERID NUMBER(10,0) NOT NULL,
    QUEUEID NUMBER(10,0) NOT NULL,
    QUEUETYPE NUMBER(10,0) NOT NULL,
    NAME NVARCHAR2(256) NOT NULL,
    DESCRIPTION NVARCHAR2(2000),
    CREATEDON DATE NOT NULL,
    CREATEDBY NUMBER(10,0) NOT NULL,
    LASTMODIFIEDON DATE NOT NULL,
    LASTMODIFIEDBY NUMBER(10,0) NOT NULL,
    DEFAULTOWNERID NUMBER(10,0) NOT NULL,
    STARTTIME DATE,
    ENDTIME DATE,
    ISACTIVE NUMBER(1,0) NOT NULL,
    EXECUTIONORDER NUMBER(10,0) NOT NULL,
    BUSINESSUNITID NUMBER(10,0) NOT NULL,
    ASSIGNMENTONLYLOGGEDINUSER NUMBER(1,0) NOT NULL,
    UNIQUEID CHAR(36 CHAR) NOT NULL,
    LASTMODIFIEDBYTYPE NUMBER(10,0) NOT NULL,
    STARTMIN NUMBER,
    ENDMIN NUMBER,
    QUEUECRITERIA NCLOB,
    IPADDRESS NVARCHAR2(50),
    CONSTRAINT PK_QUEUE PRIMARY KEY (QUEUEID)
)
"""

QUEUE_COLUMNS = [
    "OWNERID", "QUEUEID", "QUEUETYPE", "NAME", "DESCRIPTION", "CREATEDON", "CREATEDBY",
    "LASTMODIFIEDON", "LASTMODIFIEDBY", "DEFAULTOWNERID", "STARTTIME", "ENDTIME",
    "ISACTIVE", "EXECUTIONORDER", "BUSINESSUNITID", "ASSIGNMENTONLYLOGGEDINUSER",
    "UNIQUEID", "LASTMODIFIEDBYTYPE", "STARTMIN", "ENDMIN", "QUEUECRITERIA", "IPADDRESS",
]
_QUEUE_DATE_COLS = {"CREATEDON", "LASTMODIFIEDON", "STARTTIME", "ENDTIME"}
_QUEUE_STR_COLS = {"NAME", "DESCRIPTION", "UNIQUEID", "QUEUECRITERIA", "IPADDRESS"}


def queue_rows() -> list[tuple]:
    return [
        tuple(
            csv_date(r[c]) if c in _QUEUE_DATE_COLS
            else csv_str(r[c]) if c in _QUEUE_STR_COLS
            else csv_int(r[c])
            for c in QUEUE_COLUMNS
        )
        for r in read_csv_rows(CMS_DIR / "queue.csv")
    ]


QUEUEMEMBERS_DDL = """
CREATE TABLE QUEUEMEMBERS (
    OWNERID NUMBER(10,0) NOT NULL,
    QUEUEID NUMBER(10,0) NOT NULL,
    QUEUETYPE NUMBER(10,0),
    MEMBERID NUMBER(10,0) NOT NULL,
    LASTMODIFIEDBYTYPE NUMBER(10,0) NOT NULL,
    ADDEDBY NUMBER(10,0) NOT NULL,
    SHOWQUEUEMEMBERS NUMBER(10,0),
    IPADDRESS NVARCHAR2(50),
    CONSTRAINT PK_QUEUEMEMBERS PRIMARY KEY (QUEUEID, MEMBERID),
    CONSTRAINT FK_QUEUEMEMBERS_QUEUE FOREIGN KEY (QUEUEID) REFERENCES QUEUE (QUEUEID)
)
"""

QUEUEMEMBERS_COLUMNS = [
    "OWNERID", "QUEUEID", "QUEUETYPE", "MEMBERID", "LASTMODIFIEDBYTYPE", "ADDEDBY",
    "SHOWQUEUEMEMBERS", "IPADDRESS",
]


def queuemembers_rows() -> list[tuple]:
    return [
        tuple(
            csv_str(r[c]) if c == "IPADDRESS" else csv_int(r[c])
            for c in QUEUEMEMBERS_COLUMNS
        )
        for r in read_csv_rows(CMS_DIR / "queuemembers.csv")
    ]


# CASES DDL is inferred from cases.xlsx's headers -- not a verbatim reuse. CREATEDON /
# COMPLAINTCLOSEDON are Excel date-serials (via excel_date()); FACTS and SPEAKING_ORDER
# are free text, some over 4000 chars, so both are capped/truncated instead of using CLOB
# (a LOB round-trip is unnecessary risk for a demo read over async oracledb).
CASES_DDL = """
CREATE TABLE CASES (
    COMPLAINT_NO VARCHAR2(20) NOT NULL,
    STATUS_CODE VARCHAR2(30),
    BANK_NAME VARCHAR2(50),
    BANK_BRANCH_NAME VARCHAR2(100),
    DISTRICT_NAME VARCHAR2(100),
    STATE_NAME VARCHAR2(50),
    SUB_CATEGORY VARCHAR2(200),
    COMPLAINT_SUBCATEGORY VARCHAR2(300),
    CREATED_ON DATE,
    CLOSURE_CLAUSE VARCHAR2(30),
    COMPLAINANT_CATEGORY VARCHAR2(30),
    COMPLAINANT_NAME VARCHAR2(100),
    COMPLAINT_CLOSED_ON DATE,
    FACTS VARCHAR2(4000),
    SPEAKING_ORDER VARCHAR2(4000),
    CONSTRAINT PK_CASES PRIMARY KEY (COMPLAINT_NO)
)
"""

CASES_COLUMNS = [
    "COMPLAINT_NO", "STATUS_CODE", "BANK_NAME", "BANK_BRANCH_NAME", "DISTRICT_NAME",
    "STATE_NAME", "SUB_CATEGORY", "COMPLAINT_SUBCATEGORY", "CREATED_ON", "CLOSURE_CLAUSE",
    "COMPLAINANT_CATEGORY", "COMPLAINANT_NAME", "COMPLAINT_CLOSED_ON", "FACTS",
    "SPEAKING_ORDER",
]
# Maps each CASES column back to its source xlsx header (they differ -- see module docstring).
_CASES_SOURCE = {
    "COMPLAINT_NO": "Compaint No.", "STATUS_CODE": "STATUSCODE", "BANK_NAME": "BANK_NAME",
    "BANK_BRANCH_NAME": "BANK_BRANCH_NAME", "DISTRICT_NAME": "DISTRICTNAME",
    "STATE_NAME": "STATENAME", "SUB_CATEGORY": "SUBCATEGORY1",
    "COMPLAINT_SUBCATEGORY": "COMPLAINT_SUBCATEGORY_2", "CREATED_ON": "CREATEDON",
    "CLOSURE_CLAUSE": "CLOSURE_CLAUSE", "COMPLAINANT_CATEGORY": "COMPLAINANT_CATEGORY",
    "COMPLAINANT_NAME": "COMPLAINTNAME", "COMPLAINT_CLOSED_ON": "COMPLAINTCLOSEDON",
    "FACTS": "FACTS", "SPEAKING_ORDER": "SPEAKING_ORDER",
}


def cases_rows() -> list[tuple]:
    rows = []
    for r in read_xlsx_rows(CMS_DIR / "cases.xlsx"):
        rows.append((
            r[_CASES_SOURCE["COMPLAINT_NO"]], r[_CASES_SOURCE["STATUS_CODE"]],
            r[_CASES_SOURCE["BANK_NAME"]], r[_CASES_SOURCE["BANK_BRANCH_NAME"]],
            r[_CASES_SOURCE["DISTRICT_NAME"]], r[_CASES_SOURCE["STATE_NAME"]],
            r[_CASES_SOURCE["SUB_CATEGORY"]], r[_CASES_SOURCE["COMPLAINT_SUBCATEGORY"]],
            excel_date(r[_CASES_SOURCE["CREATED_ON"]]), r[_CASES_SOURCE["CLOSURE_CLAUSE"]],
            r[_CASES_SOURCE["COMPLAINANT_CATEGORY"]], r[_CASES_SOURCE["COMPLAINANT_NAME"]],
            excel_date(r[_CASES_SOURCE["COMPLAINT_CLOSED_ON"]]),
            truncate(r[_CASES_SOURCE["FACTS"]], 4000),
            truncate(r[_CASES_SOURCE["SPEAKING_ORDER"]], 4000),
        ))
    return rows


CMS_TABLES = [
    Table("REGIONS", REGIONS_DDL, REGIONS_COLUMNS, regions_rows),
    Table("QUEUE", QUEUE_DDL, QUEUE_COLUMNS, queue_rows),
    Table("QUEUEMEMBERS", QUEUEMEMBERS_DDL, QUEUEMEMBERS_COLUMNS, queuemembers_rows),
    Table("CASES", CASES_DDL, CASES_COLUMNS, cases_rows),
]

# ------------------------------------------------------------------------- DAKSH
# Neither source file has a natural unique key, so both tables get a surrogate ID
# (row position) as primary key.

COMPLAINTS_DDL = """
CREATE TABLE COMPLAINTS (
    ID NUMBER NOT NULL,
    COMPLAINT_DATE DATE,
    BANK_NAME VARCHAR2(20),
    SUBJECT VARCHAR2(200),
    COMPLAINT_CONTENT VARCHAR2(4000),
    CONSTRAINT PK_COMPLAINTS PRIMARY KEY (ID)
)
"""
COMPLAINTS_COLUMNS = ["ID", "COMPLAINT_DATE", "BANK_NAME", "SUBJECT", "COMPLAINT_CONTENT"]


def complaints_rows() -> list[tuple]:
    return [
        (
            i, excel_date(r["Date"]), r["Bank Name"], r["Subject"],
            truncate(r["Content of complaint"], 4000),
        )
        for i, r in enumerate(read_xlsx_rows(DAKSH_DIR / "DAKSH_Complaints.xlsx"), start=1)
    ]


INSPECTION_REPORTS_DDL = """
CREATE TABLE INSPECTION_REPORTS (
    ID NUMBER NOT NULL,
    REPORT_YEAR NUMBER(4,0),
    BANK_NAME VARCHAR2(20),
    PARA_NO VARCHAR2(20),
    REPORT_NAME VARCHAR2(50),
    OBSERVATION VARCHAR2(4000),
    CONSTRAINT PK_INSPECTION_REPORTS PRIMARY KEY (ID)
)
"""
INSPECTION_REPORTS_COLUMNS = ["ID", "REPORT_YEAR", "BANK_NAME", "PARA_NO", "REPORT_NAME", "OBSERVATION"]


def inspection_reports_rows() -> list[tuple]:
    return [
        (
            i, r["Year"], r["Bank Name"], r["Para No."], r["Report Name"],
            truncate(r["Observation"], 4000),
        )
        for i, r in enumerate(read_xlsx_rows(DAKSH_DIR / "Daksh_inspection_reports.xlsx"), start=1)
    ]


DAKSH_TABLES = [
    Table("COMPLAINTS", COMPLAINTS_DDL, COMPLAINTS_COLUMNS, complaints_rows),
    Table("INSPECTION_REPORTS", INSPECTION_REPORTS_DDL, INSPECTION_REPORTS_COLUMNS, inspection_reports_rows),
]


# ------------------------------------------------------------------------- runner

def connect(user: str, password: str) -> oracledb.Connection:
    host = os.environ.get("ORACLE_HOST", "localhost")
    port = os.environ.get("ORACLE_PORT", "1521")
    service = os.environ.get("ORACLE_SERVICE_NAME", "FREEPDB1")
    return oracledb.connect(user=user, password=password, dsn=f"{host}:{port}/{service}")


def recreate_table(cur: oracledb.Cursor, name: str, ddl: str) -> None:
    try:
        cur.execute(f"DROP TABLE {name} CASCADE CONSTRAINTS")
    except oracledb.DatabaseError as exc:
        (error,) = exc.args
        if error.code != 942:  # ORA-00942: table or view does not exist
            raise
    cur.execute(ddl)


def seed_schema(user: str, password: str, tables: list[Table]) -> dict[str, tuple[int, int]]:
    """Recreates and loads every table for one user/schema, then verifies row counts.
    Returns {table: (expected, actual)}."""
    conn = connect(user, password)
    try:
        cur = conn.cursor()
        expected: dict[str, int] = {}
        for table in tables:
            rows = table.rows_fn()
            recreate_table(cur, table.name, table.ddl)
            insert_sql = table.insert_sql()
            for i in range(0, len(rows), BATCH_SIZE):
                cur.executemany(insert_sql, rows[i : i + BATCH_SIZE])
            expected[table.name] = len(rows)
        conn.commit()

        actual: dict[str, tuple[int, int]] = {}
        for name, count in expected.items():
            cur.execute(f"SELECT COUNT(*) FROM {name}")
            (actual_count,) = cur.fetchone()
            actual[name] = (count, actual_count)
        return actual
    finally:
        conn.close()


def main() -> int:
    try:
        cms_counts = seed_schema("CMS", "cms", CMS_TABLES)
        daksh_counts = seed_schema("DAKSH", "daksh", DAKSH_TABLES)
    except oracledb.DatabaseError as exc:
        print(f"Could not connect/seed Oracle: {exc}", file=sys.stderr)
        print(
            "Oracle may still be initialising -- first boot of the container takes "
            "3-5 minutes. Wait for `docker compose ps` to show the oracle service as "
            "healthy, then retry.",
            file=sys.stderr,
        )
        return 1

    print("\nRow counts:")
    ok = True
    for schema, counts in [("CMS", cms_counts), ("DAKSH", daksh_counts)]:
        for table, (expected, actual) in counts.items():
            status = "OK" if expected == actual else "MISMATCH"
            if expected != actual:
                ok = False
            print(f"  {schema}.{table:<20} expected={expected:<6} actual={actual:<6} {status}")

    if not ok:
        print("\nRow count mismatch -- seeding did not complete cleanly.", file=sys.stderr)
        return 1

    print("\nSeed complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

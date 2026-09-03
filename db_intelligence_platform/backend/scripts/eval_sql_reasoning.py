#!/usr/bin/env python3
"""Does turning off chain-of-thought reasoning degrade generated SQL correctness?

Uses the app's REAL prompt (src/agents/query/prompts/generate_sql.txt), REAL response
schema (src.agents.query.schemas.SqlPlan), and REAL parser (src.utils.helpers.
parse_llm_json). Context is hand-built from a live introspection of the CMS/DAKSH
Oracle schemas -- see the module docstring in the task for why: it is the same shape
ContextRetriever produces (a list of DatabaseSchema dicts) without depending on
Neo4j/Elasticsearch state that may or may not be onboarded.

For each (question, mode) cell, generates SQL `--repeats` times, executes it against the
live Oracle DB, and scores it. Sequential requests only -- the free NIM tier 503s under
concurrent load, and a sibling agent is hitting it right now.

Usage:
    .venv/bin/python scripts/eval_sql_reasoning.py [--questions N] [--modes on,off] [--repeats 3]
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean

import oracledb
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so `src.*` imports resolve when run from anywhere

from src.agents.query.schemas import SqlPlan  # noqa: E402
from src.utils.helpers import LLMResponseError, json_dumps, load_prompt, parse_llm_json  # noqa: E402

load_dotenv(ROOT / ".env")

import os  # noqa: E402

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_BASE_URL = os.environ["OPENAI_BASE_URL"]
MODEL = os.environ["DEFAULT_LLM_MODEL"]

ORACLE_DSN = "localhost:1521/FREEPDB1"
SCHEMA_CREDS = {"CMS": "cms", "DAKSH": "daksh"}
REQUEST_TIMEOUT = 180.0
RETRY_DELAYS = [5, 15, 45]  # escalating backoff, up to 3 retries on a 503
JSON_MODE = {"type": "json_object"}

MODES: dict[str, dict] = {
    "on": {},
    "off": {"extra_body": {"chat_template_kwargs": {"thinking": "off"}}},
}

QUESTIONS = [
    "How many complaint cases are there for each bank?",
    "How many supervisory inspection observations were recorded per year?",
    "Which state has the most complaint cases, broken down by category?",
    "What are the top 5 districts by number of complaints?",
    "How many complaints were closed vs still open?",
    "Which bank had the most inspection observations in 2024?",
    "How many queue members are assigned to each queue? Show the queue name and member count.",
    "What is the average number of days between complaint creation and closure, for cases that are closed?",
    "How many complaints were filed in each month, according to the DAKSH complaints table?",
]


# --------------------------------------------------------------------------- context

SAMPLE_TEXT_LIMIT = 200  # LOB columns (FACTS etc.) can be paragraphs long -- truncate for the prompt


def _cell_to_jsonable(value):
    """Reads LOB columns eagerly (they go stale once the cursor/connection closes) and
    truncates long text so one FACTS column doesn't blow up the context payload."""
    if isinstance(value, oracledb.LOB):
        value = value.read()
    if isinstance(value, str) and len(value) > SAMPLE_TEXT_LIMIT:
        value = value[:SAMPLE_TEXT_LIMIT] + "..."
    return value


def _row_to_jsonable(row: tuple, colnames: list[str]) -> dict:
    return {name: _cell_to_jsonable(v) for name, v in zip(colnames, row)}


def introspect_schema(database_id: str, user: str, password: str) -> dict:
    """Live-introspect one Oracle schema into the same shape ContextRetriever's
    DatabaseSchema.model_dump() produces: {database_id, database_name, conn_str, tables:[...]}."""
    conn = oracledb.connect(user=user, password=password, dsn=ORACLE_DSN)
    try:
        cur = conn.cursor()
        cur.execute("SELECT table_name FROM user_tables ORDER BY table_name")
        table_names = [r[0] for r in cur.fetchall()]

        tables = []
        for table in table_names:
            cur.execute(
                "SELECT column_name, data_type FROM user_tab_columns "
                "WHERE table_name = :t ORDER BY column_id",
                t=table,
            )
            columns = [
                {"name": name, "type": dtype, "description": None, "sample_values": [], "is_entity_key": False}
                for name, dtype in cur.fetchall()
            ]
            colnames = [c["name"] for c in columns]

            sample_cur = conn.cursor()
            sample_cur.execute(f"SELECT * FROM {table} FETCH FIRST 3 ROWS ONLY")  # noqa: S608 -- table name from user_tables, not user input
            sample_data = [_row_to_jsonable(row, colnames) for row in sample_cur.fetchall()]

            tables.append({"name": table, "columns": columns, "foreign_keys": [], "sample_data": sample_data})

        return {"database_id": database_id, "database_name": database_id, "conn_str": f"oracle://{user}:***@localhost:1521/FREEPDB1", "tables": tables}
    finally:
        conn.close()


def build_context() -> tuple[list[dict], set[str]]:
    """Both schemas, every table -- the real system would narrow this via entity
    matching, but hand-including everything is the less-fragile stand-in (no dependency
    on Neo4j/Elasticsearch onboarding state) and treats both reasoning modes identically."""
    available = [introspect_schema(db_id, user, pw) for db_id, (user, pw) in
                 (("CMS", ("CMS", "cms")), ("DAKSH", ("DAKSH", "daksh")))]
    all_columns = {
        col["name"].upper()
        for db in available
        for tbl in db["tables"]
        for col in tbl["columns"]
    }
    return available, all_columns


# --------------------------------------------------------------------------- plausibility heuristics

def _split_top_level_commas(text: str) -> list[str]:
    """Split a SELECT list on commas, ignoring commas nested inside parens."""
    parts, depth, current = [], 0, []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def check_select_aliases(sql: str, known_columns: set[str]) -> list[str]:
    """Heuristic catch for the failure we've already been burned by once: the model
    emitting `SELECT NULL AS x` or aliasing an unrelated real column as the requested
    one (e.g. `bank_branch_name AS bank_name`)."""
    issues = []
    if re.search(r"\bNULL\s+AS\s+\w+", sql, re.I):
        issues.append("NULL AS <alias> in SELECT list")

    match = re.search(r"select\s+(.*?)\s+from\s", sql, re.I | re.S)
    if not match:
        return issues
    for item in _split_top_level_commas(match.group(1)):
        m = re.match(r"^\s*([\w.]+)\s+as\s+(\w+)\s*$", item.strip(), re.I)
        if not m:
            continue
        expr_col = m.group(1).split(".")[-1].upper()
        alias = m.group(2).upper()
        if expr_col != alias and expr_col in known_columns and alias in known_columns:
            issues.append(f"suspicious alias: {m.group(1).strip()} AS {m.group(2).strip()} "
                           f"(aliases real column {expr_col} as different real column {alias})")
    return issues


# --------------------------------------------------------------------------- LLM call

def _is_503(exc: Exception) -> bool:
    text = str(exc)
    return "503" in text or "ResourceExhausted" in text or getattr(exc, "status_code", None) == 503


def call_llm(client: OpenAI, prompt: str, extra: dict) -> tuple[str | None, float | None, Exception | None]:
    """One structured completion, retrying a 503 up to len(RETRY_DELAYS) times."""
    attempt = 0
    while True:
        try:
            t0 = time.monotonic()
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format=JSON_MODE,
                timeout=REQUEST_TIMEOUT,
                **extra,
            )
            latency = time.monotonic() - t0
            content = resp.choices[0].message.content if resp.choices else None
            return content, latency, None
        except Exception as exc:  # noqa: BLE001 -- recorded as an error cell, never crashes the run
            if _is_503(exc) and attempt < len(RETRY_DELAYS):
                time.sleep(RETRY_DELAYS[attempt])
                attempt += 1
                continue
            return None, None, exc


# --------------------------------------------------------------------------- Oracle execution

def execute_sql(oracle_conns: dict[str, oracledb.Connection], database_id: str, sql: str):
    """Runs `sql` against the schema named by `database_id`. Returns (columns, rows, error_str)."""
    conn = oracle_conns.get(database_id.upper()) if database_id else None
    if conn is None:
        return None, None, f"Unknown/unmapped target_database_id: {database_id!r}"
    try:
        cur = conn.cursor()
        cur.execute(sql)
        colnames = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(500)
        return colnames, rows, None
    except oracledb.Error as exc:
        return None, None, str(exc).strip()
    except Exception as exc:  # noqa: BLE001
        return None, None, str(exc).strip()


# --------------------------------------------------------------------------- scoring

@dataclass
class RunResult:
    question: str
    mode: str
    repeat: int
    latency: float | None = None
    parses: bool = False
    executes: bool = False
    plausible: bool = False
    sql: str = ""
    error: str = ""
    row_count: int = 0


def score_one(question: str, mode: str, repeat: int, client: OpenAI, context_str: str,
              known_columns: set[str], oracle_conns: dict) -> RunResult:
    result = RunResult(question=question, mode=mode, repeat=repeat)
    prompt = load_prompt("query", "generate_sql", context_str=context_str, question=question)

    content, latency, exc = call_llm(client, prompt, MODES[mode])
    result.latency = latency
    if exc is not None:
        result.error = f"LLM call failed: {exc}"
        return result

    try:
        plan: SqlPlan = parse_llm_json(content, SqlPlan)
    except LLMResponseError as e:
        result.error = f"parse failure: {e}"
        return result
    result.parses = True
    result.sql = plan.sql

    columns, rows, err = execute_sql(oracle_conns, plan.target_database_id, plan.sql)
    if err is not None:
        result.error = err
        return result
    result.executes = True
    result.row_count = len(rows)

    alias_issues = check_select_aliases(plan.sql, known_columns)
    result.plausible = result.row_count > 0 and not alias_issues
    if alias_issues:
        result.error = "; ".join(alias_issues)
    return result


# --------------------------------------------------------------------------- reporting

def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "n/a"


def render_report(results: list[RunResult]) -> str:
    lines = ["# Reasoning on/off: does it degrade generated SQL?\n"]
    lines.append("| Question | Mode | parses | executes | plausible | avg latency (s) |")
    lines.append("|---|---|---|---|---|---|")

    by_qm: dict[tuple[str, str], list[RunResult]] = {}
    for r in results:
        by_qm.setdefault((r.question, r.mode), []).append(r)

    for question in QUESTIONS:
        for mode in MODES:
            cell = by_qm.get((question, mode))
            if not cell:
                continue
            n = len(cell)
            lat = [r.latency for r in cell if r.latency is not None]
            lines.append(
                f"| {question} | {mode} | {pct(sum(r.parses for r in cell), n)} "
                f"| {pct(sum(r.executes for r in cell), n)} "
                f"| {pct(sum(r.plausible for r in cell), n)} "
                f"| {mean(lat):.1f} |" if lat else
                f"| {question} | {mode} | {pct(sum(r.parses for r in cell), n)} "
                f"| {pct(sum(r.executes for r in cell), n)} "
                f"| {pct(sum(r.plausible for r in cell), n)} | n/a |"
            )

    lines.append("\n## Per-mode totals\n")
    lines.append("| Mode | parses | executes | plausible | avg latency (s) | n |")
    lines.append("|---|---|---|---|---|---|")
    totals = {}
    for mode in MODES:
        cell = [r for r in results if r.mode == mode]
        if not cell:
            continue
        n = len(cell)
        lat = [r.latency for r in cell if r.latency is not None]
        totals[mode] = {
            "parses": sum(r.parses for r in cell),
            "executes": sum(r.executes for r in cell),
            "plausible": sum(r.plausible for r in cell),
            "n": n,
        }
        lines.append(
            f"| {mode} | {pct(totals[mode]['parses'], n)} | {pct(totals[mode]['executes'], n)} "
            f"| {pct(totals[mode]['plausible'], n)} | {mean(lat):.1f} | {n} |"
            if lat else
            f"| {mode} | {pct(totals[mode]['parses'], n)} | {pct(totals[mode]['executes'], n)} "
            f"| {pct(totals[mode]['plausible'], n)} | n/a | {n} |"
        )

    lines.append("\n## Verdict\n")
    if "on" in totals and "off" in totals and totals["on"]["n"] and totals["off"]["n"]:
        on_rate = totals["on"]["plausible"] / totals["on"]["n"]
        off_rate = totals["off"]["plausible"] / totals["off"]["n"]
        drop = on_rate - off_rate
        safe = drop <= 0.05  # a >5pp plausibility drop is treated as a real regression
        verdict = "YES" if safe else "NO"
        lines.append(
            f"**Is it safe to disable reasoning on generate_sql: {verdict}.**\n\n"
            f"Plausible-SQL rate: reasoning ON = {on_rate:.0%}, reasoning OFF = {off_rate:.0%} "
            f"(delta {drop:+.0%}). "
            + ("No material degradation observed at this sample size." if safe else
               "Reasoning OFF produces meaningfully worse SQL -- do not disable it on generate_sql "
               "without further mitigation (e.g. a stricter retry/validation loop).")
        )
    else:
        lines.append("Insufficient data to render a verdict (one or both modes produced zero results).")

    failures = [r for r in results if r.parses and not r.plausible]
    if failures:
        lines.append("\n## Bad SQL (verbatim)\n")
        for r in failures:
            lines.append(f"### [{r.mode}] repeat {r.repeat}: {r.question}")
            lines.append(f"Error/issue: {r.error or '(no rows returned)'}")
            lines.append("```sql\n" + r.sql + "\n```\n")

    return "\n".join(lines)


# --------------------------------------------------------------------------- self-test

def _selftest() -> None:
    """Cheap, no-network sanity check for the two bits of actual logic in this script."""
    assert _split_top_level_commas("a, b, f(c, d), e") == ["a", " b", " f(c, d)", " e"]
    known = {"BANK_NAME", "STATE_NAME", "DISTRICT_NAME"}
    assert check_select_aliases("SELECT NULL AS state_name FROM cases", known) == ["NULL AS <alias> in SELECT list"]
    assert check_select_aliases(
        "SELECT district_name AS state_name FROM cases", known
    ) == ["suspicious alias: district_name AS state_name (aliases real column DISTRICT_NAME as different real column STATE_NAME)"]
    assert check_select_aliases("SELECT COUNT(*) AS total, bank_name FROM cases GROUP BY bank_name", known) == []
    assert not _is_503(ValueError("boom"))
    assert _is_503(Exception("503 ResourceExhausted: Worker local total request limit reached (16/16)"))


# --------------------------------------------------------------------------- main

def main() -> None:
    _selftest()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=int, default=len(QUESTIONS), help="Use only the first N questions")
    parser.add_argument("--modes", type=str, default="on,off", help="Comma-separated subset of: on,off")
    parser.add_argument("--repeats", type=int, default=3, help="Samples per (question, mode) cell")
    args = parser.parse_args()

    questions = QUESTIONS[: args.questions]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    for m in modes:
        if m not in MODES:
            parser.error(f"Unknown mode {m!r}, choose from {list(MODES)}")

    print(f"Introspecting live Oracle schemas (CMS, DAKSH) ...", file=sys.stderr)
    available, known_columns = build_context()
    context_str = json_dumps(available)
    print(f"Context built: {sum(len(d['tables']) for d in available)} tables, "
          f"{len(known_columns)} distinct column names, {len(context_str)} chars.", file=sys.stderr)

    oracle_conns = {db_id: oracledb.connect(user=user, password=pw, dsn=ORACLE_DSN)
                    for db_id, (user, pw) in (("CMS", ("CMS", "cms")), ("DAKSH", ("DAKSH", "daksh")))}

    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

    total_cells = len(questions) * len(modes) * args.repeats
    print(f"Running {total_cells} calls STRICTLY SEQUENTIALLY "
          f"({len(questions)} questions x {len(modes)} modes x {args.repeats} repeats) ...", file=sys.stderr)

    results: list[RunResult] = []
    done = 0
    for question in questions:
        for mode in modes:
            for repeat in range(1, args.repeats + 1):
                r = score_one(question, mode, repeat, client, context_str, known_columns, oracle_conns)
                results.append(r)
                done += 1
                status = "OK" if r.plausible else ("EXEC-FAIL" if not r.executes else "IMPLAUSIBLE")
                lat = f"{r.latency:.1f}s" if r.latency else "n/a"
                print(f"[{done}/{total_cells}] {mode:>3} rep{repeat} {status:<11} {lat:>7}  {question[:60]}",
                      file=sys.stderr)
                time.sleep(1)  # be polite to a rate-limited free tier shared with a sibling agent

    for conn in oracle_conns.values():
        conn.close()

    report = render_report(results)
    print("\n" + report)


if __name__ == "__main__":
    main()

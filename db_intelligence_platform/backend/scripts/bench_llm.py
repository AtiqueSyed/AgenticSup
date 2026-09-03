"""Benchmark: does chain-of-thought reasoning buy us anything on this app's real prompts?

For every prompt this app actually sends (src/agents/*/prompts/*.txt, rendered with
realistic sample data), calls the NVIDIA NIM endpoint under three reasoning modes and
measures latency, token usage, and whether the reply still parses against the app's own
pydantic schema. That last column is the point: a mode that's 5x faster but returns
unparseable JSON is not a usable mode.

Standalone -- does not import or touch src/clients/llm.py or src/core/config.py. It
only imports the prompt-loading helper, the response parser, and the pydantic schemas,
all read-only.

Usage (run from `backend/`):

    .venv/bin/python scripts/bench_llm.py --repeats 1 --prompts decompose_query,generate_sql
    .venv/bin/python scripts/bench_llm.py --json /tmp/bench.json
    .venv/bin/python scripts/bench_llm.py --model nvidia/nemotron-3.5-lightning-30b-a3b

Reasoning modes (see LLM_REASONING notes in src/core/config.py for the production
toggle this data justifies):
  on          -- pass nothing extra; the model reasons by default.
  off         -- extra_body={"chat_template_kwargs": {"thinking": "off"}}
  effort_low  -- extra_body={"reasoning_effort": "low"}

Known NOT to work on this endpoint (excluded): `max_thinking_tokens` (HTTP 400) and
`thinking: {"budget_tokens": N}` (accepted but silently ignored).
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import dotenv_values  # noqa: E402
from openai import AsyncOpenAI, APIConnectionError, APIStatusError, APITimeoutError  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from src.agents.onboarding.schemas import EntityExtraction, EntityKeyMap, TableSemantics  # noqa: E402
from src.agents.query.schemas import SqlPlan, SubQuestions, VisualizationSpec  # noqa: E402
from src.schemas.domain import DatabaseSchema, TableSchema  # noqa: E402
from src.utils.helpers import LLMResponseError, json_dumps, load_prompt, parse_llm_json  # noqa: E402

_ENV = dotenv_values(BACKEND_ROOT / ".env")


def _env(key: str, default: str = "") -> str:
    import os

    return os.environ.get(key) or _ENV.get(key) or default


DEFAULT_MODEL = _env("DEFAULT_LLM_MODEL", "nvidia/nemotron-3-super-120b-a12b")
API_KEY = _env("OPENAI_API_KEY")
BASE_URL = _env("OPENAI_BASE_URL", "https://integrate.api.nvidia.com/v1")

REQUEST_TIMEOUT_S = 180.0
MAX_ATTEMPTS = 3
BACKOFF_SCHEDULE_S = (5, 15, 30)  # escalating backoff between retries on 503

REASONING_MODES: dict[str, dict[str, Any] | None] = {
    "on": None,
    "off": {"chat_template_kwargs": {"thinking": "off"}},
    "effort_low": {"reasoning_effort": "low"},
}

# ------------------------------------------------------------------ realistic sample data
#
# Sizes are meant to mirror production, not toy inputs: the real generate_sql context
# is the two databases below with their columns and a few sample rows, which lands
# generate_sql's rendered prompt around ~3700 tokens -- the same order of magnitude a
# real onboarded schema produces.

CMS_TABLES = [
    TableSchema(
        name="CASES",
        columns=[
            {"name": "COMPLAINT_NO", "type": "VARCHAR2(30)", "sample_values": ["CMS/2024/00123", "CMS/2024/00124"]},
            {"name": "STATUS_CODE", "type": "VARCHAR2(10)", "sample_values": ["OPEN", "CLOSED", "PENDING"]},
            {"name": "BANK_NAME", "type": "VARCHAR2(100)", "sample_values": ["HDFC Bank", "State Bank of India", "ICICI Bank"]},
            {"name": "BANK_BRANCH_NAME", "type": "VARCHAR2(150)", "sample_values": ["Andheri West", "Connaught Place", "MG Road"]},
            {"name": "DISTRICT_NAME", "type": "VARCHAR2(100)", "sample_values": ["Mumbai", "New Delhi", "Bengaluru Urban"]},
            {"name": "STATE_NAME", "type": "VARCHAR2(100)", "sample_values": ["Maharashtra", "Delhi", "Karnataka"]},
            {"name": "SUB_CATEGORY", "type": "VARCHAR2(100)", "sample_values": ["ATM/Debit Card", "Loans", "Deposits"]},
            {"name": "COMPLAINT_SUBCATEGORY", "type": "VARCHAR2(150)", "sample_values": ["Unauthorized transaction", "Delay in loan disbursement"]},
            {"name": "CREATED_ON", "type": "DATE", "sample_values": ["2024-01-15", "2024-02-03"]},
            {"name": "CLOSURE_CLAUSE", "type": "VARCHAR2(50)", "sample_values": ["9.1", "9.2"]},
            {"name": "COMPLAINANT_CATEGORY", "type": "VARCHAR2(50)", "sample_values": ["Individual", "Business"]},
            {"name": "COMPLAINANT_NAME", "type": "VARCHAR2(150)", "sample_values": ["Rohit Sharma", "Anita Desai"]},
            {"name": "COMPLAINT_CLOSED_ON", "type": "DATE", "sample_values": ["2024-02-20"]},
            {"name": "FACTS", "type": "CLOB", "sample_values": ["Complainant alleges an unauthorized ATM withdrawal of Rs 25000 on a card reported lost two days earlier."]},
            {"name": "SPEAKING_ORDER", "type": "CLOB", "sample_values": ["Based on the evidence submitted, the bank is directed to reverse the disputed transaction within 15 days."]},
        ],
        foreign_keys=[
            {"column": "BANK_NAME", "references_table": "REGIONS", "references_column": "STATE_NAME"},
        ],
        sample_data=[
            {"COMPLAINT_NO": "CMS/2024/00123", "STATUS_CODE": "CLOSED", "BANK_NAME": "HDFC Bank", "STATE_NAME": "Maharashtra", "SUB_CATEGORY": "ATM/Debit Card", "DISTRICT_NAME": "Mumbai", "COMPLAINANT_CATEGORY": "Individual"},
            {"COMPLAINT_NO": "CMS/2024/00124", "STATUS_CODE": "OPEN", "BANK_NAME": "ICICI Bank", "STATE_NAME": "Karnataka", "SUB_CATEGORY": "Loans", "DISTRICT_NAME": "Bengaluru Urban", "COMPLAINANT_CATEGORY": "Business"},
            {"COMPLAINT_NO": "CMS/2024/00125", "STATUS_CODE": "PENDING", "BANK_NAME": "State Bank of India", "STATE_NAME": "Delhi", "SUB_CATEGORY": "Deposits", "DISTRICT_NAME": "New Delhi", "COMPLAINANT_CATEGORY": "Individual"},
            {"COMPLAINT_NO": "CMS/2024/00126", "STATUS_CODE": "CLOSED", "BANK_NAME": "Axis Bank", "STATE_NAME": "Maharashtra", "SUB_CATEGORY": "ATM/Debit Card", "DISTRICT_NAME": "Pune", "COMPLAINANT_CATEGORY": "Individual"},
            {"COMPLAINT_NO": "CMS/2024/00127", "STATUS_CODE": "CLOSED", "BANK_NAME": "HDFC Bank", "STATE_NAME": "Maharashtra", "SUB_CATEGORY": "Loans", "DISTRICT_NAME": "Mumbai", "COMPLAINANT_CATEGORY": "Business"},
            {"COMPLAINT_NO": "CMS/2024/00128", "STATUS_CODE": "OPEN", "BANK_NAME": "Punjab National Bank", "STATE_NAME": "Punjab", "SUB_CATEGORY": "Deposits", "DISTRICT_NAME": "Ludhiana", "COMPLAINANT_CATEGORY": "Individual"},
            {"COMPLAINT_NO": "CMS/2024/00129", "STATUS_CODE": "PENDING", "BANK_NAME": "ICICI Bank", "STATE_NAME": "Karnataka", "SUB_CATEGORY": "ATM/Debit Card", "DISTRICT_NAME": "Bengaluru Urban", "COMPLAINANT_CATEGORY": "Individual"},
            {"COMPLAINT_NO": "CMS/2024/00130", "STATUS_CODE": "CLOSED", "BANK_NAME": "State Bank of India", "STATE_NAME": "Delhi", "SUB_CATEGORY": "Loans", "DISTRICT_NAME": "New Delhi", "COMPLAINANT_CATEGORY": "Business"},
        ],
    ),
    TableSchema(
        name="REGIONS",
        columns=[
            {"name": "REGION_ID", "type": "NUMBER", "sample_values": ["1", "2"]},
            {"name": "REGION_NAME", "type": "VARCHAR2(100)", "sample_values": ["Western Region", "Northern Region"]},
            {"name": "STATE_NAME", "type": "VARCHAR2(100)", "sample_values": ["Maharashtra", "Delhi"]},
        ],
    ),
    TableSchema(
        name="QUEUE",
        columns=[
            {"name": "QUEUE_ID", "type": "NUMBER", "sample_values": ["101", "102"]},
            {"name": "QUEUE_NAME", "type": "VARCHAR2(100)", "sample_values": ["L1 Adjudication", "L2 Review"]},
        ],
    ),
    TableSchema(
        name="QUEUEMEMBERS",
        columns=[
            {"name": "QUEUE_ID", "type": "NUMBER", "sample_values": ["101", "102"]},
            {"name": "USER_ID", "type": "VARCHAR2(50)", "sample_values": ["U1001", "U1002"]},
        ],
    ),
]

DAKSH_TABLES = [
    TableSchema(
        name="COMPLAINTS",
        columns=[
            {"name": "ID", "type": "NUMBER", "sample_values": ["1", "2"]},
            {"name": "COMPLAINT_DATE", "type": "DATE", "sample_values": ["2024-03-01", "2024-03-02"]},
            {"name": "BANK_NAME", "type": "VARCHAR2(100)", "sample_values": ["HDFC Bank", "Axis Bank"]},
            {"name": "SUBJECT", "type": "VARCHAR2(200)", "sample_values": ["Delay in KYC update", "Wrong interest charged"]},
            {"name": "COMPLAINT_CONTENT", "type": "CLOB", "sample_values": ["Customer reports that the branch has not updated KYC despite three visits."]},
        ],
        sample_data=[
            {"ID": 1, "COMPLAINT_DATE": "2024-03-01", "BANK_NAME": "HDFC Bank", "SUBJECT": "Delay in KYC update"},
            {"ID": 2, "COMPLAINT_DATE": "2024-03-02", "BANK_NAME": "Axis Bank", "SUBJECT": "Wrong interest charged"},
            {"ID": 3, "COMPLAINT_DATE": "2024-03-05", "BANK_NAME": "HDFC Bank", "SUBJECT": "ATM did not dispense cash but account debited"},
            {"ID": 4, "COMPLAINT_DATE": "2024-03-09", "BANK_NAME": "Punjab National Bank", "SUBJECT": "Loan foreclosure charges not waived"},
        ],
    ),
    TableSchema(
        name="INSPECTION_REPORTS",
        columns=[
            {"name": "ID", "type": "NUMBER", "sample_values": ["1", "2"]},
            {"name": "REPORT_YEAR", "type": "NUMBER", "sample_values": ["2023", "2024"]},
            {"name": "BANK_NAME", "type": "VARCHAR2(100)", "sample_values": ["HDFC Bank", "Axis Bank"]},
            {"name": "PARA_NO", "type": "VARCHAR2(20)", "sample_values": ["3.2", "4.1"]},
            {"name": "REPORT_NAME", "type": "VARCHAR2(200)", "sample_values": ["Annual Financial Inspection 2023"]},
            {"name": "OBSERVATION", "type": "CLOB", "sample_values": ["Branch failed to report suspicious transactions within the mandated timeline."]},
        ],
        sample_data=[
            {"ID": 1, "REPORT_YEAR": 2023, "BANK_NAME": "HDFC Bank", "PARA_NO": "3.2", "OBSERVATION": "Branch failed to report suspicious transactions within the mandated timeline."},
            {"ID": 2, "REPORT_YEAR": 2024, "BANK_NAME": "Axis Bank", "PARA_NO": "4.1", "OBSERVATION": "KYC documents not periodically refreshed for high-risk accounts."},
            {"ID": 3, "REPORT_YEAR": 2024, "BANK_NAME": "HDFC Bank", "PARA_NO": "2.5", "OBSERVATION": "Delay in credit of NEFT transactions beyond RBI-mandated window."},
        ],
    ),
]

AVAILABLE_DATABASES = [
    DatabaseSchema(database_id="CMS", database_name="CMS", conn_str="oracle+oracledb_async://CMS@host/FREEPDB1", tables=CMS_TABLES).model_dump(),
    DatabaseSchema(database_id="DAKSH", database_name="DAKSH", conn_str="oracle+oracledb_async://DAKSH@host/FREEPDB1", tables=DAKSH_TABLES).model_dump(),
]

EXTRACTED_TABLES = [t.model_dump() for t in CMS_TABLES + DAKSH_TABLES]

SEMANTICS = {
    "CASES": "Individual consumer complaint cases handled by the ombudsman, including status and resolution.",
    "REGIONS": "Geographic regions used to route and report on cases.",
    "QUEUE": "Work queues used to route cases to adjudicating officers.",
    "QUEUEMEMBERS": "Mapping of officers to the queues they work.",
    "COMPLAINTS": "Raw customer complaints filed against banks.",
    "INSPECTION_REPORTS": "Findings from supervisory inspections of banks.",
}

ENTITIES_SUMMARY = [
    {"id": "CustomerGrievance", "mapped_tables": ["CASES", "COMPLAINTS"]},
    {"id": "RespondentBank", "mapped_tables": ["CASES", "COMPLAINTS", "INSPECTION_REPORTS"]},
    {"id": "InspectionFinding", "mapped_tables": ["INSPECTION_REPORTS"]},
]

QUERY_RESULT_ROWS = [
    {"BANK_NAME": "HDFC Bank", "COMPLAINT_COUNT": 482},
    {"BANK_NAME": "ICICI Bank", "COMPLAINT_COUNT": 361},
    {"BANK_NAME": "State Bank of India", "COMPLAINT_COUNT": 795},
    {"BANK_NAME": "Axis Bank", "COMPLAINT_COUNT": 210},
]

COMPLEX_QUESTION = (
    "Show me all complaint cases for HDFC Bank in Maharashtra closed in the last year, "
    "and separately tell me the average number of inspection observations recorded per bank branch."
)
SIMPLE_QUESTION = "How many complaint cases are there for each bank?"


def _schema_summary(tables: list[dict[str, Any]], semantics: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Same shape as src.agents.onboarding.nodes._schema_summary -- reproduced here
    rather than imported since that helper is module-private."""
    summary = []
    for table in tables:
        entry: dict[str, Any] = {"table": table["name"]}
        if semantics is not None:
            entry["purpose"] = semantics.get(table["name"], "")
        entry["columns"] = [{"name": c["name"], "type": c.get("type", ""), "samples": c.get("sample_values", [])[:3]} for c in table["columns"]]
        summary.append(entry)
    return summary


class PromptSpec(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    name: str
    agent: str
    prompt_file: str
    variables: dict[str, Any]
    schema_cls: type[BaseModel] | None


PROMPT_SPECS = [
    PromptSpec(
        name="decompose_query",
        agent="query",
        prompt_file="decompose_query",
        variables={"question": COMPLEX_QUESTION},
        schema_cls=SubQuestions,
    ),
    PromptSpec(
        name="generate_sql",
        agent="query",
        prompt_file="generate_sql",
        variables={"context_str": json_dumps(AVAILABLE_DATABASES), "question": SIMPLE_QUESTION},
        schema_cls=SqlPlan,
    ),
    PromptSpec(
        name="recommend_visualizations",
        agent="query",
        prompt_file="recommend_visualizations",
        variables={"sample_data": json_dumps(QUERY_RESULT_ROWS)},
        schema_cls=VisualizationSpec,
    ),
    PromptSpec(
        name="synthesize_answer",
        agent="query",
        prompt_file="synthesize_answer",
        variables={"question": SIMPLE_QUESTION, "results_str": json_dumps(QUERY_RESULT_ROWS)},
        schema_cls=None,
    ),
    PromptSpec(
        name="generate_semantics",
        agent="onboarding",
        prompt_file="generate_semantics",
        variables={"schema_summary": json_dumps(_schema_summary(EXTRACTED_TABLES))},
        schema_cls=TableSemantics,
    ),
    PromptSpec(
        name="identify_entities",
        agent="onboarding",
        prompt_file="identify_entities",
        variables={
            "existing_entities_context": json_dumps([]),
            "schema_summary": json_dumps(_schema_summary(EXTRACTED_TABLES, SEMANTICS)),
        },
        schema_cls=EntityExtraction,
    ),
    PromptSpec(
        name="map_entity_columns",
        agent="onboarding",
        prompt_file="map_entity_columns",
        variables={
            "schema_summary": json_dumps([{"table": t["name"], "columns": [c["name"] for c in t["columns"]]} for t in EXTRACTED_TABLES]),
            "entities_summary": json_dumps(ENTITIES_SUMMARY),
        },
        schema_cls=EntityKeyMap,
    ),
]
PROMPT_BY_NAME = {p.name: p for p in PROMPT_SPECS}


# --------------------------------------------------------------------------------- run one cell


async def call_once(client: AsyncOpenAI, model: str, prompt_text: str, extra_body: dict[str, Any] | None, json_mode: bool) -> dict[str, Any]:
    """One HTTP call with retry-on-503 and escalating backoff. Returns a raw record
    with an "error" key set on unrecoverable failure instead of raising, so a bad cell
    doesn't crash the whole matrix."""
    kwargs: dict[str, Any] = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if extra_body:
        kwargs["extra_body"] = extra_body

    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        start = time.monotonic()
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt_text}],
                timeout=REQUEST_TIMEOUT_S,
                **kwargs,
            )
        except (APIStatusError, APIConnectionError, APITimeoutError) as exc:
            last_error = str(exc)
            is_retryable = isinstance(exc, (APIConnectionError, APITimeoutError)) or getattr(exc, "status_code", None) in (429, 503)
            if not is_retryable or attempt == MAX_ATTEMPTS:
                return {"latency_s": time.monotonic() - start, "error": last_error}
            backoff = BACKOFF_SCHEDULE_S[min(attempt - 1, len(BACKOFF_SCHEDULE_S) - 1)]
            print(f"    attempt {attempt} failed ({last_error[:80]}), retrying in {backoff}s", file=sys.stderr)
            await asyncio.sleep(backoff)
            continue

        latency_s = time.monotonic() - start
        message = response.choices[0].message
        usage = response.usage
        return {
            "latency_s": latency_s,
            "content": message.content,
            "reasoning_content": getattr(message, "reasoning_content", None),
            "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
            "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
            "error": None,
        }

    return {"latency_s": 0.0, "error": last_error or "unknown failure"}


def validate(content: str | None, schema_cls: type[BaseModel] | None) -> tuple[bool | None, str | None]:
    """(valid, error). valid is None when the prompt has no schema (synthesize_answer) --
    there's nothing to validate, so it's neither a pass nor a fail."""
    if schema_cls is None:
        return None, None
    try:
        parse_llm_json(content, schema_cls)
        return True, None
    except LLMResponseError as exc:
        return False, str(exc)


# --------------------------------------------------------------------------------- main


async def run_matrix(model: str, prompt_names: list[str], mode_names: list[str], repeats: int) -> list[dict[str, Any]]:
    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL, max_retries=0, timeout=REQUEST_TIMEOUT_S)
    records: list[dict[str, Any]] = []
    try:
        for prompt_name in prompt_names:
            spec = PROMPT_BY_NAME[prompt_name]
            prompt_text = load_prompt(spec.agent, spec.prompt_file, **spec.variables)
            for mode_name in mode_names:
                extra_body = REASONING_MODES[mode_name]
                for repeat_idx in range(repeats):
                    print(f"[{prompt_name} / {mode_name}] run {repeat_idx + 1}/{repeats} ...", file=sys.stderr, flush=True)
                    raw = await call_once(client, model, prompt_text, extra_body, json_mode=spec.schema_cls is not None)
                    valid, val_error = (None, None) if raw.get("error") else validate(raw.get("content"), spec.schema_cls)
                    record = {
                        "prompt": prompt_name,
                        "mode": mode_name,
                        "repeat": repeat_idx,
                        "latency_s": round(raw["latency_s"], 2),
                        "prompt_tokens": raw.get("prompt_tokens"),
                        "completion_tokens": raw.get("completion_tokens"),
                        "reasoning_len": len(raw.get("reasoning_content") or ""),
                        "content_len": len(raw.get("content") or ""),
                        "valid": valid,
                        "validation_error": val_error,
                        "error": raw.get("error"),
                        "content": (raw.get("content") or "")[:4000],
                        "reasoning_content": (raw.get("reasoning_content") or "")[:4000],
                    }
                    records.append(record)
                    status = "ERROR: " + record["error"] if record["error"] else f"{record['latency_s']}s valid={valid}"
                    print(f"    -> {status}", file=sys.stderr, flush=True)
    finally:
        await client.close()
    return records


def summarize(records: list[dict[str, Any]], prompt_names: list[str], mode_names: list[str]) -> list[dict[str, Any]]:
    cells = []
    for prompt_name in prompt_names:
        for mode_name in mode_names:
            cell_records = [r for r in records if r["prompt"] == prompt_name and r["mode"] == mode_name]
            ok = [r for r in cell_records if not r["error"]]
            latencies = [r["latency_s"] for r in ok]
            completion_tokens = [r["completion_tokens"] for r in ok if r["completion_tokens"] is not None]
            reasoning_lens = [r["reasoning_len"] for r in ok]
            valid_flags = [r["valid"] for r in ok]
            all_valid = all(v is not False for v in valid_flags) and len(ok) == len(cell_records)
            cells.append(
                {
                    "prompt": prompt_name,
                    "mode": mode_name,
                    "n": len(cell_records),
                    "n_errors": len(cell_records) - len(ok),
                    "median_latency_s": round(statistics.median(latencies), 2) if latencies else None,
                    "median_completion_tokens": round(statistics.median(completion_tokens)) if completion_tokens else None,
                    "median_reasoning_len": round(statistics.median(reasoning_lens)) if reasoning_lens else None,
                    "all_valid": all_valid,
                    "has_schema": any(v is not None for v in valid_flags) or not valid_flags,
                }
            )
    return cells


def print_report(cells: list[dict[str, Any]], prompt_names: list[str], mode_names: list[str]) -> None:
    print("\n| Prompt | Mode | Median Latency (s) | Median Out Tokens | Median Reasoning Chars | Valid? | Errors |")
    print("|---|---|---|---|---|---|---|")
    for cell in cells:
        valid_str = "n/a" if cell["median_latency_s"] is None else ("PASS" if cell["all_valid"] else "FAIL")
        print(
            f"| {cell['prompt']} | {cell['mode']} | {cell['median_latency_s']} | "
            f"{cell['median_completion_tokens']} | {cell['median_reasoning_len']} | {valid_str} | {cell['n_errors']}/{cell['n']} |"
        )

    print("\nRecommendation (fastest mode that stayed valid across all repeats):")
    for prompt_name in prompt_names:
        prompt_cells = [c for c in cells if c["prompt"] == prompt_name]
        candidates = [c for c in prompt_cells if c["all_valid"] and c["median_latency_s"] is not None]
        if not candidates:
            print(f"  {prompt_name}: NO MODE stayed valid across all repeats -- inspect errors before disabling reasoning.")
            continue
        best = min(candidates, key=lambda c: c["median_latency_s"])
        baseline = next((c["median_latency_s"] for c in prompt_cells if c["mode"] == "on"), None)
        speedup = f" ({baseline / best['median_latency_s']:.1f}x vs 'on')" if baseline and best["mode"] != "on" else ""
        print(f"  {prompt_name}: {best['mode']}{speedup}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--modes", default=",".join(REASONING_MODES), help="comma-separated subset of: " + ",".join(REASONING_MODES))
    parser.add_argument("--prompts", default=",".join(PROMPT_BY_NAME), help="comma-separated subset of: " + ",".join(PROMPT_BY_NAME))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--json", dest="json_path", default=None, help="dump raw per-run records to this path")
    args = parser.parse_args()

    if not API_KEY:
        parser.error("OPENAI_API_KEY not found in environment or .env")

    mode_names = [m.strip() for m in args.modes.split(",") if m.strip()]
    prompt_names = [p.strip() for p in args.prompts.split(",") if p.strip()]
    for m in mode_names:
        if m not in REASONING_MODES:
            parser.error(f"unknown mode {m!r}, choose from {list(REASONING_MODES)}")
    for p in prompt_names:
        if p not in PROMPT_BY_NAME:
            parser.error(f"unknown prompt {p!r}, choose from {list(PROMPT_BY_NAME)}")

    print(f"Model: {args.model}  Modes: {mode_names}  Prompts: {prompt_names}  Repeats: {args.repeats}", file=sys.stderr)
    records = asyncio.run(run_matrix(args.model, prompt_names, mode_names, args.repeats))

    if args.json_path:
        Path(args.json_path).write_text(json.dumps(records, indent=2))
        print(f"\nRaw records written to {args.json_path}", file=sys.stderr)

    cells = summarize(records, prompt_names, mode_names)
    print_report(cells, prompt_names, mode_names)


if __name__ == "__main__":
    main()

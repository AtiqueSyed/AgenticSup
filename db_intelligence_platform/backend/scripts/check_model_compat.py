"""Preflight compatibility report: will swapping the LLM model break the app?

Runs a fixed, small (~12 call) sequence of real requests against an OpenAI-compatible
endpoint and checks the exact assumptions ``src/clients/llm.py`` and
``src/utils/helpers.py`` depend on: entitlement, JSON mode, reasoning placement, the
``chat_template_kwargs: {"thinking": "off"}`` switch, and -- the check that matters
most -- whether the app's real ``generate_sql`` / ``decompose_query`` prompts still
produce schema-valid JSON via the app's own ``parse_llm_json``.

Standalone: does not import or touch ``src/clients/llm.py`` or ``src/core/config.py``.
Only imports the prompt-loading helper, the response parser, and the pydantic schemas
those two modules also use -- all read-only. Not NVIDIA-specific: the JSON-mode and
reasoning-switch probes are generic OpenAI-compatible requests; only the "reasoning
switch" probe body (``chat_template_kwargs``) is NIM/vLLM-specific and is labelled as
such in its report line.

Usage (run from `backend/`):

    .venv/bin/python scripts/check_model_compat.py --model nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
    .venv/bin/python scripts/check_model_compat.py --model <id> --base-url https://on-prem-host/v1 --json out.json

Exit code is non-zero if any check FAILs (usable as a CI gate).
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import dotenv_values  # noqa: E402
from openai import (  # noqa: E402
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    BadRequestError,
    NotFoundError,
)
from pydantic import BaseModel  # noqa: E402

from src.agents.query.schemas import SqlPlan, SubQuestions  # noqa: E402
from src.schemas.domain import DatabaseSchema, TableSchema  # noqa: E402
from src.utils.helpers import LLMResponseError, json_dumps, load_prompt, parse_llm_json  # noqa: E402

_ENV = dotenv_values(BACKEND_ROOT / ".env")


def _env(key: str, default: str = "") -> str:
    import os

    return os.environ.get(key) or _ENV.get(key) or default


REQUEST_TIMEOUT_S = 180.0
MAX_ATTEMPTS = 3
BACKOFF_SCHEDULE_S = (10, 30, 60)  # escalating backoff on 503 -- endpoint is heavily contended
THINKING_OFF = {"chat_template_kwargs": {"thinking": "off"}}
JSON_MODE = {"type": "json_object"}

# ------------------------------------------------------------------------- sample data
# Small, self-contained fixture for generate_sql's context -- not imported from
# bench_llm.py (this file is meant to be standalone) but the same shape as the real
# DatabaseSchema the app builds.

_TABLES = [
    TableSchema(
        name="CASES",
        columns=[
            {"name": "COMPLAINT_NO", "type": "VARCHAR2(30)", "sample_values": ["CMS/2024/00123"]},
            {"name": "STATUS_CODE", "type": "VARCHAR2(10)", "sample_values": ["OPEN", "CLOSED"]},
            {"name": "BANK_NAME", "type": "VARCHAR2(100)", "sample_values": ["HDFC Bank", "ICICI Bank"]},
            {"name": "STATE_NAME", "type": "VARCHAR2(100)", "sample_values": ["Maharashtra", "Karnataka"]},
            {"name": "CREATED_ON", "type": "DATE", "sample_values": ["2024-01-15"]},
        ],
        sample_data=[
            {"COMPLAINT_NO": "CMS/2024/00123", "STATUS_CODE": "CLOSED", "BANK_NAME": "HDFC Bank", "STATE_NAME": "Maharashtra"},
            {"COMPLAINT_NO": "CMS/2024/00124", "STATUS_CODE": "OPEN", "BANK_NAME": "ICICI Bank", "STATE_NAME": "Karnataka"},
        ],
    ),
]
_AVAILABLE_DATABASES = [
    DatabaseSchema(database_id="CMS", database_name="CMS", conn_str="oracle+oracledb_async://CMS@host/FREEPDB1", tables=_TABLES).model_dump()
]
_GENERATE_SQL_PROMPT = load_prompt(
    "query", "generate_sql", context_str=json_dumps(_AVAILABLE_DATABASES), question="How many complaints are there for each bank?"
)
_DECOMPOSE_PROMPT = load_prompt(
    "query",
    "decompose_query",
    question="Show me all complaints for HDFC Bank in Maharashtra, and separately the average inspection score per bank.",
)
_LATENCY_PROMPT = load_prompt(
    "query", "synthesize_answer", question="Which bank has the most complaints?", results_str=json_dumps([{"BANK_NAME": "HDFC Bank", "COUNT": 482}])
)


# ------------------------------------------------------------------------------ calling


@dataclass
class CallResult:
    ok: bool
    latency_s: float
    content: str | None = None
    reasoning_content: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    error: str | None = None
    not_entitled: bool = False  # a clean 404 -- model exists on the endpoint's list but this key can't call it


async def call(client: AsyncOpenAI, model: str, prompt: str, *, json_mode: bool = False, extra_body: dict | None = None) -> CallResult:
    """One chat-completion, retried on 503 with escalating backoff. Never raises --
    every failure mode (network, auth, 404, 400, provider-200-with-error-body) comes
    back as a ``CallResult`` with ``ok=False`` so a bad probe can't crash the report."""
    kwargs: dict[str, Any] = {}
    if json_mode:
        kwargs["response_format"] = JSON_MODE
    if extra_body:
        kwargs["extra_body"] = extra_body

    last_error = "unknown failure"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        start = time.monotonic()
        try:
            response = await client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}], timeout=REQUEST_TIMEOUT_S, **kwargs
            )
        except NotFoundError as exc:
            return CallResult(ok=False, latency_s=time.monotonic() - start, error=str(exc), not_entitled=True)
        except BadRequestError as exc:
            return CallResult(ok=False, latency_s=time.monotonic() - start, error=str(exc))
        except (APIConnectionError, APITimeoutError) as exc:
            last_error = str(exc)
            if attempt == MAX_ATTEMPTS:
                return CallResult(ok=False, latency_s=time.monotonic() - start, error=last_error)
        except APIStatusError as exc:
            last_error = str(exc)
            is_retryable = exc.status_code in (429, 503)
            if not is_retryable or attempt == MAX_ATTEMPTS:
                return CallResult(ok=False, latency_s=time.monotonic() - start, error=last_error)
        else:
            latency_s = time.monotonic() - start
            if not response.choices:
                # Some gateways answer an auth/model error with HTTP 200 and an
                # ``error`` body instead of raising -- see llm.py::_first_choice.
                error = getattr(response, "error", None) or {}
                if isinstance(error, dict):
                    error = error.get("error", error)
                    detail = error.get("message") if isinstance(error, dict) else str(error)
                else:
                    detail = str(error)
                return CallResult(ok=False, latency_s=latency_s, error=f"no choices in response: {detail or response}")
            message = response.choices[0].message
            usage = response.usage
            return CallResult(
                ok=True,
                latency_s=latency_s,
                content=message.content,
                reasoning_content=getattr(message, "reasoning_content", None),
                prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
                completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
            )
        backoff = BACKOFF_SCHEDULE_S[min(attempt - 1, len(BACKOFF_SCHEDULE_S) - 1)]
        print(f"    attempt {attempt} failed ({last_error[:100]}), retrying in {backoff}s", file=sys.stderr)
        await asyncio.sleep(backoff)
    return CallResult(ok=False, latency_s=0.0, error=last_error)


# ------------------------------------------------------------------------------ checks


@dataclass
class Check:
    name: str
    verdict: str  # PASS / FAIL / WARN / SKIP
    evidence: str


@dataclass
class Report:
    model: str
    base_url: str
    checks: list[Check] = field(default_factory=list)
    verdict: str = ""

    def add(self, name: str, verdict: str, evidence: str) -> None:
        self.checks.append(Check(name, verdict, evidence))
        print(f"  [{verdict:4s}] {name}: {evidence}")


def _reasoning_len(result: CallResult) -> int:
    """Chars of chain-of-thought, wherever the model put it: a separate
    ``reasoning_content`` field, or ``<think>...</think>`` inlined in ``content``."""
    if result.reasoning_content:
        return len(result.reasoning_content)
    content = result.content or ""
    start = content.lower().find("<think>")
    if start == -1:
        return 0
    end = content.lower().find("</think>", start)
    return len(content[start:end]) if end != -1 else len(content) - start


def _validate(result: CallResult, model_cls: type[BaseModel]) -> tuple[bool, str]:
    if not result.ok:
        return False, f"call failed: {result.error}"
    try:
        parsed = parse_llm_json(result.content, model_cls)
        return True, f"validated OK: {parsed.model_dump()}"
    except LLMResponseError as exc:
        return False, f"schema validation failed: {exc}. Raw content: {(result.content or '')[:200]!r}"


async def run_checks(client: AsyncOpenAI, model: str, base_url: str) -> Report:
    report = Report(model=model, base_url=base_url)

    # 1. Reachable / entitled -----------------------------------------------------
    print("\n[1] reachable / entitled")
    reach = await call(client, model, "Reply with exactly the single word: OK", extra_body=THINKING_OFF)
    if not reach.ok:
        if reach.not_entitled:
            report.add("reachable", "FAIL", f"404 not entitled -- model is not callable with this key: {reach.error}")
        else:
            report.add("reachable", "FAIL", f"network/auth/provider error (not a 404): {reach.error}")
        # Every other check calls this same model -- there is nothing left to learn.
        for name in ("json_mode", "reasoning_placement", "reasoning_switch", "structured_output_generate_sql",
                     "structured_output_decompose_query", "latency"):
            report.add(name, "SKIP", "skipped -- model is not reachable")
        report.verdict = f"DO NOT SWAP: {reach.error}"
        return report
    report.add("reachable", "PASS", f"trivial completion succeeded in {reach.latency_s:.1f}s, reply={reach.content!r}")

    # 2. JSON mode -----------------------------------------------------------------
    print("\n[2] JSON mode")
    json_probe = await call(client, model, 'Return only this JSON object, nothing else: {"status": "ok"}', json_mode=True, extra_body=THINKING_OFF)
    if not json_probe.ok:
        if "response_format" in (json_probe.error or ""):
            report.add("json_mode", "PASS", f"provider rejects response_format with 400 -- the app's fallback (drop it, retry) will actually trigger: {json_probe.error[:150]}")
        else:
            report.add("json_mode", "WARN", f"call failed for an unrelated reason, JSON mode unverified: {json_probe.error}")
    else:
        try:
            payload = json.loads((json_probe.content or "").strip())
            report.add("json_mode", "PASS", f"HTTP 200, response_format honored, valid JSON returned: {payload}")
        except json.JSONDecodeError:
            report.add(
                "json_mode", "FAIL",
                f"HTTP 200 but response_format was SILENTLY IGNORED (not valid JSON, and the app's 400-triggered "
                f"fallback never fires). Raw content: {(json_probe.content or '')[:200]!r}",
            )

    # 3 & 4. Reasoning placement + switch, using the app's real generate_sql AND
    # decompose_query prompts -- two independent pairs, since a single sample of
    # reasoning length is noisy (reasoning length varies call to call even with
    # identical settings) and this is the check that already bit the team once.
    print("\n[3&4] reasoning placement / switch (generate_sql + decompose_query, reasoning on vs off)")
    sql_on = await call(client, model, _GENERATE_SQL_PROMPT, json_mode=True)
    sql_off = await call(client, model, _GENERATE_SQL_PROMPT, json_mode=True, extra_body=THINKING_OFF)
    decompose_off = await call(client, model, _DECOMPOSE_PROMPT, json_mode=True, extra_body=THINKING_OFF)
    decompose_on = await call(client, model, _DECOMPOSE_PROMPT, json_mode=True)

    if not sql_on.ok:
        report.add("reasoning_placement", "WARN", f"could not probe placement -- reasoning-on call failed: {sql_on.error}")
    elif sql_on.reasoning_content:
        report.add("reasoning_placement", "PASS", f"separate reasoning_content field ({len(sql_on.reasoning_content)} chars); content is clean JSON, _THINK_RE in helpers.py is NOT needed for this model")
    elif "<think>" in (sql_on.content or "").lower():
        report.add("reasoning_placement", "WARN", "chain-of-thought is INLINED as <think> tags in content -- _THINK_RE in src/utils/helpers.py IS load-bearing for this model")
    else:
        report.add("reasoning_placement", "WARN", "no reasoning_content and no <think> tag detected on this prompt -- inconclusive (model may not have reasoned, or reasoning was already off)")

    pairs = [("generate_sql", sql_on, sql_off), ("decompose_query", decompose_on, decompose_off)]
    ratios: list[float] = []
    pair_evidence: list[str] = []
    for label, on_result, off_result in pairs:
        if not (on_result.ok and off_result.ok):
            pair_evidence.append(f"{label}: could not compare (on.ok={on_result.ok} off.ok={off_result.ok})")
            continue
        on_len, off_len = _reasoning_len(on_result), _reasoning_len(off_result)
        on_tok, off_tok = on_result.completion_tokens or 0, off_result.completion_tokens or 0
        pair_evidence.append(f"{label}: reasoning_chars on={on_len} off={off_len}, completion_tokens on={on_tok} off={off_tok}")
        if on_len > 0:
            ratios.append(off_len / on_len)

    evidence = "; ".join(pair_evidence)
    if not ratios:
        report.add("reasoning_switch", "WARN", f"neither prompt produced detectable on-mode reasoning to compare against -- switch effect inconclusive ({evidence})")
    else:
        # Worst case across the two prompts: one prompt "working" isn't enough --
        # this is exactly the accepted-but-ignored failure mode we've been burned by.
        worst_ratio = max(ratios)
        if worst_ratio <= 0.5:
            report.add("reasoning_switch", "PASS", f"thinking=off measurably cuts reasoning on every prompt tested (worst case {worst_ratio:.0%} of on-mode): {evidence}")
        elif worst_ratio <= 0.9:
            report.add("reasoning_switch", "WARN", f"switch has only a PARTIAL effect on at least one prompt ({worst_ratio:.0%} of on-mode reasoning remains) -- do not assume it fully disables thinking: {evidence}")
        else:
            report.add("reasoning_switch", "FAIL", f"HTTP 200 accepted the switch but at least one prompt showed NO meaningful reduction (accepted-but-ignored, {worst_ratio:.0%} of on-mode remains): {evidence}")

    # 5. Structured-output validity, end to end ------------------------------------
    print("\n[5] structured-output validity (generate_sql -> SqlPlan, decompose_query -> SubQuestions)")
    ok_on, ev_on = _validate(sql_on, SqlPlan)
    ok_off, ev_off = _validate(sql_off, SqlPlan)
    if ok_on and ok_off:
        report.add("structured_output_generate_sql", "PASS", f"SqlPlan validated with reasoning on AND off. on: {ev_on}; off: {ev_off}")
    elif ok_on or ok_off:
        which = "reasoning ON" if ok_on else "reasoning OFF"
        report.add("structured_output_generate_sql", "WARN", f"SqlPlan only validates with {which} (prod runs generate_sql with reasoning ON by default -- LLM_REASONING_OFF_OPERATIONS does not include it). on: {ev_on}; off: {ev_off}")
    else:
        report.add("structured_output_generate_sql", "FAIL", f"SqlPlan failed to validate in both modes. on: {ev_on}; off: {ev_off}")

    ok_doff, ev_doff = _validate(decompose_off, SubQuestions)
    ok_don, ev_don = _validate(decompose_on, SubQuestions)
    if ok_doff:
        # This is the config the app actually runs (decompose_query is in
        # LLM_REASONING_OFF_OPERATIONS by default) -- it is the one that must pass.
        report.add("structured_output_decompose_query", "PASS", f"SubQuestions validated in prod's actual config (reasoning off): {ev_doff}")
    else:
        report.add("structured_output_decompose_query", "FAIL", f"SubQuestions failed in prod's actual config (reasoning off): {ev_doff}. reasoning-on attempt: {'ok' if ok_don else ev_don}")

    # 6. Latency baseline ------------------------------------------------------------
    print("\n[6] latency baseline (median of 3 calls per mode, synthesize_answer-shaped prompt)")
    on_latencies = [sql_on.latency_s, decompose_on.latency_s]
    off_latencies = [sql_off.latency_s, decompose_off.latency_s]
    extra_on = await call(client, model, _LATENCY_PROMPT)
    extra_off = await call(client, model, _LATENCY_PROMPT, extra_body=THINKING_OFF)
    if extra_on.ok:
        on_latencies.append(extra_on.latency_s)
    if extra_off.ok:
        off_latencies.append(extra_off.latency_s)

    if on_latencies and off_latencies:
        med_on, med_off = statistics.median(on_latencies), statistics.median(off_latencies)
        report.add(
            "latency", "PASS" if max(med_on, med_off) < REQUEST_TIMEOUT_S else "WARN",
            f"median latency reasoning-on={med_on:.1f}s (n={len(on_latencies)}), reasoning-off={med_off:.1f}s (n={len(off_latencies)})",
        )
    else:
        report.add("latency", "WARN", "not enough successful calls to compute a median")

    # -------------------------------------------------------------------------- verdict
    fails = [c for c in report.checks if c.verdict == "FAIL"]
    warns = [c for c in report.checks if c.verdict == "WARN"]
    if fails:
        report.verdict = "DO NOT SWAP: " + "; ".join(f"{c.name} FAILED ({c.evidence[:120]})" for c in fails)
    elif warns:
        report.verdict = "SWAP WITH CHANGES: " + "; ".join(f"{c.name}: {c.evidence[:120]}" for c in warns)
    else:
        report.verdict = "SAFE TO SWAP"
    return report


def print_table(report: Report) -> None:
    print(f"\n{'=' * 90}\nModel compatibility report: {report.model}\nEndpoint: {report.base_url}\n{'=' * 90}")
    print(f"{'CHECK':38s} {'VERDICT':6s} EVIDENCE")
    print("-" * 90)
    for c in report.checks:
        evidence = c.evidence if len(c.evidence) <= 100 else c.evidence[:97] + "..."
        print(f"{c.name:38s} {c.verdict:6s} {evidence}")
    print("-" * 90)
    print(f"VERDICT: {report.verdict}")


async def main_async(args: argparse.Namespace) -> int:
    api_key = _env("OPENAI_API_KEY")
    base_url = args.base_url or _env("OPENAI_BASE_URL", "https://integrate.api.nvidia.com/v1")
    model = args.model or _env("DEFAULT_LLM_MODEL")
    if not api_key:
        print("error: OPENAI_API_KEY not set (checked .env and environment)", file=sys.stderr)
        return 2
    if not model:
        print("error: --model not given and DEFAULT_LLM_MODEL not set in .env", file=sys.stderr)
        return 2

    client = AsyncOpenAI(api_key=api_key, base_url=base_url, max_retries=0, timeout=REQUEST_TIMEOUT_S)
    try:
        report = await run_checks(client, model, base_url)
    finally:
        await client.close()

    print_table(report)

    if args.json:
        payload = {
            "model": report.model,
            "base_url": report.base_url,
            "verdict": report.verdict,
            "checks": [{"name": c.name, "verdict": c.verdict, "evidence": c.evidence} for c in report.checks],
        }
        Path(args.json).write_text(json.dumps(payload, indent=2))
        print(f"\nWrote JSON report to {args.json}")

    return 1 if any(c.verdict == "FAIL" for c in report.checks) else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", help="Model id to check. Defaults to DEFAULT_LLM_MODEL from .env.")
    parser.add_argument("--base-url", help="OpenAI-compatible base URL. Defaults to OPENAI_BASE_URL from .env.")
    parser.add_argument("--json", help="Write the full machine-readable report to this path.")
    args = parser.parse_args()
    sys.exit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()

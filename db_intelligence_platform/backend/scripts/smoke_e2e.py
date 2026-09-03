"""End-to-end smoke test: proves the running API actually works, over HTTP only.

Run from `backend/` with the API already up on the host:

    uv run python scripts/smoke_e2e.py
    uv run python scripts/smoke_e2e.py --skip-onboard   # reuse already-onboarded DBs

Talks only to the HTTP API (base URL from $API_BASE, default http://localhost:8000) --
never imports from `src/`, so it exercises exactly what a real client would see.
"""

import argparse
import os
import sys
import time

import httpx

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
ONBOARD_TIMEOUT_S = 600  # 7 LangGraph nodes incl. 3 LLM calls against a large model
POLL_INTERVAL_S = 5

# Mirrors src/agents/query/nodes.py -- read from source, not retyped from memory.
NO_CONTEXT_ERROR = "I could not find the relevant details or tables to answer this question."
ORA_ERROR_ANSWER = "I could not find the data you were looking for. Please ask again with more details."

CONNECTIONS = [
    ("CMS", "oracle+oracledb_async://CMS:cms@localhost:1521/?service_name=FREEPDB1"),
    ("DAKSH", "oracle+oracledb_async://DAKSH:daksh@localhost:1521/?service_name=FREEPDB1"),
]

# Three questions chosen to exercise: single-database aggregation on CMS, single-database
# aggregation on DAKSH, and a cross-database-shaped GROUP BY question -- each needs the
# LLM to pick a target database and group results, not just a point lookup.
QUESTIONS = [
    "How many complaint cases are there for each bank?",
    "How many supervisory inspection observations were recorded per year?",
    "Which state has the most complaint cases, broken down by category?",
]

results: list[tuple[str, bool, str]] = []


def report(step: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {step}" + (f" -- {detail}" if detail else ""))
    results.append((step, ok, detail))


def print_summary() -> None:
    print("\n=== Summary ===")
    for step, ok, detail in results:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {step}" + (f" -- {detail}" if detail else ""))


def check_health(client: httpx.Client) -> None:
    """Fails early (exits the whole script) if the API is not up at all -- every later
    step would just be a wall of confusing connection errors otherwise."""
    try:
        resp = client.get("/health")
    except httpx.ConnectError as exc:
        report("GET /health", False, f"API not reachable at {API_BASE}: {exc}")
        print_summary()
        sys.exit(1)
    if resp.status_code != 200:
        report("GET /health", False, f"status={resp.status_code}")
        print_summary()
        sys.exit(1)
    data = resp.json()
    provider = data.get("llm_provider", "")
    if "integrate.api.nvidia.com" not in provider:
        report("GET /health", False, f"llm_provider={provider!r} does not mention integrate.api.nvidia.com")
        return
    report("GET /health", True, f"llm_provider={provider}")


def onboard_all(client: httpx.Client) -> dict[str, str]:
    """Returns {database_name: database_id}."""
    db_ids: dict[str, str] = {}
    for name, conn_str in CONNECTIONS:
        resp = client.post("/api/v1/onboard", json={"database_name": name, "connection_string": conn_str})
        if resp.status_code != 200:
            report(f"POST /api/v1/onboard ({name})", False, f"status={resp.status_code} body={resp.text}")
            return db_ids
        db_id = resp.json()["database_id"]
        db_ids[name] = db_id
        report(f"POST /api/v1/onboard ({name})", True, f"database_id={db_id}")

    for name, db_id in db_ids.items():
        wait_for_onboarding(client, name, db_id)
    return db_ids


def wait_for_onboarding(client: httpx.Client, name: str, db_id: str) -> None:
    start = time.monotonic()
    while True:
        elapsed = time.monotonic() - start
        resp = client.get(f"/api/v1/onboard/{db_id}/status")
        status = resp.json().get("status", "unknown") if resp.status_code == 200 else f"http {resp.status_code}"
        print(f"  ... {name} onboarding: {status} ({elapsed:.0f}s elapsed)")

        if status == "completed":
            report(f"Onboard {name} completed", True, f"took {elapsed:.0f}s")
            return
        if status == "error" or status.startswith("failed:"):
            report(f"Onboard {name} completed", False, f"status={status!r}")
            return
        if elapsed > ONBOARD_TIMEOUT_S:
            report(f"Onboard {name} completed", False, f"timed out after {elapsed:.0f}s, last status={status!r}")
            return
        time.sleep(POLL_INTERVAL_S)


def check_stats(client: httpx.Client) -> None:
    resp = client.get("/api/v1/stats")
    if resp.status_code != 200:
        report("GET /api/v1/stats", False, f"status={resp.status_code}")
        return
    data = resp.json()
    total = data.get("total_databases")
    entities = data.get("entities_identified")
    if total != 2:
        report("GET /api/v1/stats", False, f"total_databases={total}, expected 2")
        return
    if not entities or entities <= 0:
        report(
            "GET /api/v1/stats",
            False,
            f"entities_identified={entities} -- the knowledge-graph node never ran (construct_knowledge_graph failed silently or found no entities)",
        )
        return
    report("GET /api/v1/stats", True, f"total_databases={total}, entities_identified={entities}")


def check_graph(client: httpx.Client) -> None:
    resp = client.get("/api/v1/graph")
    if resp.status_code != 200:
        report("GET /api/v1/graph", False, f"status={resp.status_code}")
        return
    nodes = resp.json().get("nodes", [])
    if not nodes:
        report("GET /api/v1/graph", False, "nodes list is empty")
        return
    report("GET /api/v1/graph", True, f"{len(nodes)} nodes")


def ask_questions(client: httpx.Client) -> None:
    for question in QUESTIONS:
        resp = client.post("/api/v1/query", json={"question": question})
        if resp.status_code != 200:
            report(f"POST /api/v1/query {question!r}", False, f"status={resp.status_code} body={resp.text}")
            continue
        data = resp.json()
        sql_used = data.get("sql_used")
        answer = data.get("answer", "")
        db_id = data.get("database_id")
        db_name = data.get("database_name")

        print(f"\n  Q: {question}")
        print(f"  routed to: database_id={db_id} database_name={db_name}")
        print(f"  SQL: {sql_used}")
        print(f"  A: {answer}")

        if not sql_used:
            report(f"POST /api/v1/query {question!r}", False, "sql_used is null -- no SQL was generated/executed")
            continue
        if answer in (NO_CONTEXT_ERROR, ORA_ERROR_ANSWER):
            report(f"POST /api/v1/query {question!r}", False, f"answer is the fallback string: {answer!r}")
            continue
        report(f"POST /api/v1/query {question!r}", True, f"-> {db_name or db_id}")


def load_existing_databases(client: httpx.Client) -> None:
    resp = client.get("/api/v1/stats")
    if resp.status_code != 200:
        report("GET /api/v1/stats (--skip-onboard)", False, f"status={resp.status_code}")
        return
    databases = resp.json().get("databases", [])
    if len(databases) < 2:
        report(
            "GET /api/v1/stats (--skip-onboard)",
            False,
            f"only {len(databases)} database(s) registered -- run without --skip-onboard first",
        )
        return
    report("GET /api/v1/stats (--skip-onboard)", True, f"reusing {len(databases)} already-onboarded database(s)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-onboard",
        action="store_true",
        help="Skip onboarding and jump straight to the query phase, reusing databases from /api/v1/stats",
    )
    args = parser.parse_args()

    # 300s: one /query runs up to 4 sequential LLM calls against a 120B reasoning
    # model, plus the SQL retry loop. 30s timed out before the first answer.
    with httpx.Client(base_url=API_BASE, timeout=300.0) as client:
        check_health(client)

        if args.skip_onboard:
            load_existing_databases(client)
        else:
            onboard_all(client)

        check_stats(client)
        check_graph(client)
        ask_questions(client)

    print_summary()
    if all(ok for _, ok, _ in results):
        print("\nAll checks passed.")
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()

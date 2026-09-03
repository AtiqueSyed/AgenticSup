# Handover

Everything a new developer needs to run, change, and not break this project.
Read this first, then the doc it points you at for the task you have.

---

## 1. What it is

Two LangGraph agent workflows over an Oracle database, behind FastAPI, with a React UI.

- **Onboarding** (admin, background task) — introspect a live Oracle schema, have an LLM
  describe it, extract business entities, write a Neo4j knowledge graph, embed into
  Elasticsearch.
- **Query** (user) — natural-language question → retrieve schema context → generate
  Oracle SQL → execute → synthesize an answer → recommend a chart.

Everything is observable: every agent node and every LLM call is an OpenTelemetry span,
exported to Jaeger.

## 2. Where things are

The repo nests: `AgenticSup/AgenticSup/` is the git root. This project is
`db_intelligence_platform/` inside it. Sibling `rbi_nl2sql_agents/project_data/` holds
the CSV/XLSX seed data — **not** dead weight, `scripts/seed_oracle.py` reads it.

```
db_intelligence_platform/
  docker-compose.yml    oracle, neo4j, elasticsearch, otel-collector, jaeger
                        + prometheus/grafana behind --profile metrics
                        + backend/frontend behind --profile app
  Makefile              infra / seed / api / smoke / test / ui / down / clean
  infra/                oracle init SQL, otel collector, prometheus, grafana datasources
  docs/                 RUNBOOK, TELEMETRY, MODELS  (see §3)
  backend/
    src/                the app (see §6)
    scripts/            seed_oracle, smoke_e2e, check_model_compat, bench_llm,
                        eval_sql_reasoning, check_complexity
    tests/              103 tests, no network, no live services
    API.md              every endpoint + request/response shapes + frontend call map
    .env                REAL SECRETS, gitignored. Copy .env.example to create it.
    registry.json       onboarded DBs incl. PLAINTEXT Oracle passwords. Gitignored.
  frontend_new/         the live UI (Vite + React 19). NOT `frontend/` — that is gone.
```

## 3. The other four docs

| Doc | Read it when |
|---|---|
| `docs/RUNBOOK.md` | Bringing it up, or something is broken. Has a troubleshooting table keyed to real failures. |
| `docs/TELEMETRY.md` | Reading traces; expected span trees for query and onboarding. |
| `docs/MODELS.md` | Changing the LLM, or wondering why a call takes 40 seconds. |
| `backend/API.md` | Writing against the HTTP API or the frontend. |

`backend/README.md` covers backend internals and coding standards in more depth than §6 here.

## 4. Bring it up

Prerequisite, by hand: Docker Desktop → Settings → Resources → **Memory = 6 GB**.
The stack does not fit in the 4 GB default; containers get OOM-killed as `Exited (137)`.

```bash
cd db_intelligence_platform
cp backend/.env.example backend/.env   # then fill in real values -- see §5
make infra    # first run pulls ~4.5 GB; Oracle's first boot is 3-5 min
make seed     # CMS + DAKSH schemas from ../rbi_nl2sql_agents/project_data
make api      # backend on the host, port 8000
make smoke    # end-to-end assertion; exits 0 when the platform actually works
make ui       # http://localhost:5174
```

`make clean` deletes volumes and forces the 3–5 minute Oracle re-init. Use `make down`.

Backend runs **on the host**, infra in Docker — that is why `.env` uses `localhost`
hostnames. The compose `backend` service (profile `app`) overrides them with
Docker-internal names.

Ports: 8000 API · 5174 UI · 16686 Jaeger · 7474 Neo4j · 9200 Elastic · 1521 Oracle ·
9090 Prometheus · 3000 Grafana.

## 5. Configuration that actually matters

All settings live in `backend/src/core/config.py`, validated once at startup. Secrets are
`SecretStr` so they cannot leak into a log or span. The non-obvious ones:

| Setting | Why you care |
|---|---|
| `DEFAULT_LLM_MODEL` | `nvidia/nemotron-3-super-120b-a12b`. Only three nemotrons are entitled on this NVIDIA account; everything else 404s. Read `docs/MODELS.md` before changing it. |
| `LLM_REASONING` | `on`/`off`. Global chain-of-thought default. |
| `LLM_REASONING_OFF_OPERATIONS` | Per-node override, by node name. Currently `recommend_visualizations,decompose_query,synthesize_answer`. **This is a 10× end-to-end latency knob** (52.8s → 5.1s). |
| `OTEL_CAPTURE_CONTENT` | Off by default. Turning it on ships prompts — which contain live schema and sample rows — to your tracing backend. |
| `OTEL_SDK_DISABLED` | Tests set this. |
| `MAX_SQL_RETRIES` | Bounds the `generate_sql` → `execute_sql` retry loop. |
| `REGISTRY_PATH` | Move `registry.json` out of the repo if you want the plaintext passwords elsewhere. |

Reasoning is off only for the three transient presentation nodes. It stays **on** for
`generate_sql` and for all onboarding nodes, and that is a measured decision, not
caution — `docs/MODELS.md` §"Why the config does not simply turn reasoning off
everywhere" has the evidence. Don't flip it without reading that.

## 6. Architecture

Request flow: `routes/` (thin HTTP) → `services/` (business logic) → `agents/` (LangGraph)
→ `clients/` (one thin wrapper per external system). `clients/container.py` holds them all
as one `Clients` object built during lifespan and reached via `get_clients`.

| File | What lives there |
|---|---|
| `src/main.py` | `create_app()` — middleware, telemetry, routers |
| `src/agents/base.py` | `BaseNode` — every node is a span; `state["status"] == "error"` short-circuits the rest |
| `src/agents/query/nodes.py` | the 7 query nodes; the retry loop lives in `graph.py`'s conditional edge |
| `src/agents/onboarding/nodes.py` | the 7 onboarding nodes, straight line, no retries |
| `src/agents/*/prompts/*.txt` | prompt text. Editing wording needs **no** code change |
| `src/clients/llm.py` | reasoning switch, JSON mode, retries, provider-quirk fallbacks |
| `src/utils/helpers.py` | `load_prompt`, `parse_llm_json`, `traced` |
| `src/services/registry_service.py` | file-backed registry — the source of truth for onboarded DBs |
| `src/models/` | **dead legacy SQLAlchemy models.** Not imported, not wired. Ignore them. |

Frontend: no react-router. `src/router.js` is ~30 lines of History API glue
(`useSyncExternalStore` + `popstate`); `src/routes.js` is the route table and the
role guard, deliberately React-free so `npm test` can run it under plain node.
Four routes: `/login`, `/chat`, `/admin/onboarding`, `/admin/registry`.

## 7. What each Docker container is for

Nothing here is installed on your Mac. Every service is a container. The backend is the
one thing that normally runs on the host, so it can hot-reload.

| Container | Image | Port | What it does | If it is down |
|---|---|---|---|---|
| `oracle` | `gvenzl/oracle-free:23-slim-faststart` | 1521 | **The database the platform actually queries.** Holds the `CMS` and `DAKSH` schemas that `make seed` loads. | Nothing works. |
| `neo4j` | `neo4j:5.12.0` | 7474 UI, 7687 bolt | **The knowledge graph.** Onboarding writes entities, tables, columns and relationships here. Querying reads it to find which tables can answer a question. | Onboarding and querying both fail. |
| `elasticsearch` | `elasticsearch:8.10.2` | 9200 | **Vector search.** Stores 384-dimension embeddings of entities and table descriptions in `dbintel_entities` and `dbintel_tables`. A question is embedded and matched against these to shortlist entities. | App still runs. `SearchService` does nothing and retrieval falls back to `GraphReadService.all_schemas()` — fine for two small databases, bad for many. |
| `otel-collector` | `otel/opentelemetry-collector-contrib:0.115.1` | 4317 in, 8889 out | **The one pipe all telemetry goes through.** Receives traces and metrics from the backend, sends traces to Jaeger, and publishes metrics for Prometheus to collect. | App runs normally. Traces are dropped silently. |
| `jaeger` | `jaegertracing/all-in-one:1.62.0` | 16686 | **Stores and shows traces.** This is where you look at a slow request. | You lose the trace UI only. |
| `prometheus` | `prom/prometheus:v3.0.1` | 9090 | **Stores numbers over time.** Reads the collector's `:8889` every 15 seconds. Only starts with `--profile metrics`. | You lose charts over time. |
| `grafana` | `grafana/grafana:11.4.0` | 3000 | **Dashboards.** Reads Prometheus and Jaeger, both already configured. Only starts with `--profile metrics`. | You lose dashboards. Jaeger still works on its own. |
| `backend` | built from `backend/` | 8000 | The API, containerised. Only starts with `--profile app`. Normally you run it on the host instead. | — |
| `frontend` | built from `frontend_new/` | 5174 | The UI behind nginx. Only starts with `--profile app`. | — |

Three ways to start it:

```bash
docker compose up -d --wait                    # ~4.2 GB: database + graph + search + traces
docker compose --profile metrics up -d --wait  # ~4.6 GB: adds Prometheus + Grafana  (= make infra)
docker compose --profile app up -d backend frontend   # also run the app in Docker
```

Details that will cost you time if you miss them:

- **Only Oracle and Neo4j keep their data.** They have named volumes (`oracle_data`,
  `neo4j_data`). **Elasticsearch has no volume** — `docker compose down` erases its
  index, so after a restart you must re-onboard to rebuild it, or search silently
  degrades to the graph fallback above.
- **Oracle's first boot takes 3–5 minutes** and pulls a ~2 GB image. The volume means
  you pay this once. `make clean` deletes it and you pay again.
- **`INIT_SGA_SIZE` and `INIT_PGA_SIZE` only apply on first boot.** Changing them later
  does nothing until `docker compose down -v`.
- **`CMS` and `DAKSH` are separate Oracle users with no permission to see each other's
  tables, on purpose.** `SchemaExtractor` lists every schema the login can see, so if
  they could see each other, onboarding either one would pull in both and merge them
  into a single database.
- Every heap is capped in `docker-compose.yml` (Oracle SGA 1 GB, Elasticsearch 512 MB,
  Neo4j 512 MB heap + 256 MB page cache). The defaults do not fit in 6 GB.
- Passwords here are local-dev defaults: Oracle `SYS`/`oracle` (the app never uses it),
  Neo4j `neo4j`/`password`, Elasticsearch security off, Grafana open to anyone as Admin.
  None of this is safe outside your laptop.

## 8. OpenTelemetry, Jaeger, Prometheus, Grafana

### What OpenTelemetry is, and why this project needs it

OpenTelemetry (OTel) is a standard way for an app to record what it did while handling a
request. It is a library inside the backend, not a server.

One question triggers 4–7 LLM calls plus Neo4j, Elasticsearch and Oracle calls. When a
question takes 50 seconds or returns a wrong answer, you need to know **which step** was
slow or wrong. Without traces you are guessing. This is how the 52.8s → 5.1s speed-up was
found and proved.

It records two different kinds of data:

- **Traces** — one request, broken into steps, each with a start time and a duration.
  Good for "why was *this* request slow". Kept for a short time.
- **Metrics** — plain numbers added up over time across all requests. Good for "is it
  getting slower this week" and "how often does the LLM return bad JSON".

### How the data moves

```
backend (OTel library)
   |  OTLP over gRPC, port 4317
   v
otel-collector  --traces-->  jaeger        (view at :16686)
       |
       |  publishes metrics on :8889
       v
   prometheus (scrapes every 15s)  <--reads--  grafana (:3000, also reads jaeger)
```

The collector exists so the app only knows one address. Changing where telemetry goes is
a collector-config change, not a code change.

### What produces spans

Some libraries are instrumented automatically: FastAPI, SQLAlchemy (so Oracle queries
appear), httpx (which the OpenAI SDK uses underneath), Elasticsearch, and logging. The
rest is written by hand where no instrumentation exists.

| Span name | Written in | Attributes on it |
|---|---|---|
| `POST /api/v1/query` | FastAPI, automatic | HTTP method, route, status |
| `query.<node>`, `onboarding.<node>` | `agents/base.py` | `agent.name`, `agent.node`, `db.id`, `agent.node.status` |
| `llm.<node>` | `clients/llm.py` | `gen_ai.system`, `gen_ai.request.model`, `gen_ai.operation.name`, `gen_ai.reasoning` (`on`/`off`), `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` |
| `llm.<node>.retry` | same | a retry after a schema failure shows up as its own span |
| Oracle query | SQLAlchemy, automatic | `db.system=oracle`, the statement |
| Neo4j query | `clients/neo4j.py` | the Neo4j driver has no official instrumentation, so this is manual |

Every node is a span because `BaseNode.__call__` wraps `run()` — you get this free by
subclassing, without writing any telemetry code in the node.

Every log line carries `trace=<id> span=<id>`, so you can copy an id from a log straight
into Jaeger's search box.

### The metrics, and what they tell you

The Python names use dots; Prometheus renames them (dots become underscores, counters get
`_total`, the `ms` unit becomes `milliseconds`).

| In code | In Prometheus | What it means |
|---|---|---|
| `llm.calls` | `llm_calls_total` | One per LLM call, labeled `operation` (the node name). Shows which node calls the model most. |
| `llm.validation_failures` | `llm_validation_failures_total` | The LLM returned JSON that failed its schema, labeled `operation` and `model`. **Non-zero here means the model is misbehaving** — watch this after any model swap. |
| `agent.node.duration` | `agent_node_duration_milliseconds_bucket` / `_sum` / `_count` | How long one node took, labeled `agent.name`, `agent.node`, `outcome` (`ok` or `error`). Recorded in a `finally`, so a node that fails after 30 seconds is still timed. |

### Three ways to see traces

1. **Jaeger** at <http://localhost:16686>, service `db-intelligence-backend`. The normal way.
2. **Console** — `make api-console` sets `OTEL_TRACES_EXPORTER=console` and prints spans
   as JSON to the terminal. No containers needed. Best when debugging telemetry itself.
3. **Grafana** at <http://localhost:3000>, for metrics charts with trace lookup alongside.

### Switches, and one trap

`OTEL_SDK_DISABLED=true` turns everything off (the tests use this).
`OTEL_TRACES_EXPORTER` is `otlp`, `console`, or `none`.
`OTEL_EXPORTER_OTLP_ENDPOINT` is where the collector is.
`OTEL_CAPTURE_CONTENT=true` attaches full prompts and answers to spans — off by default,
because prompts contain real schema and real sample rows from onboarded databases.

**The trap:** metrics are only exported when `OTEL_TRACES_EXPORTER` is `otlp`. Setting it
to `console` gives you traces in the terminal and **silently no metrics at all**.

Telemetry never takes the app down. If instrumentation fails it is logged and the app
continues, and if nothing is listening on 4317 the spans are just dropped.

## 9. Pydantic validation — what it does and why

**The rule: nothing crosses a boundary as a plain dict.** Every place data enters or
leaves the app, it is validated into a typed object first. There are three base classes
in `src/schemas/base.py`, one per trust level.

| Base | Used for | Setting | Why |
|---|---|---|---|
| `StrictModel` | incoming HTTP request bodies | `extra="forbid"` | An unknown field is a 422 error, not silently ignored. A caller who misspells a field name finds out immediately instead of wondering why their value had no effect. |
| `ApiModel` | outgoing HTTP responses | `populate_by_name=True` | The response shape is a fixed contract the frontend depends on. Renaming a Python field cannot accidentally change the JSON key. |
| `LenientModel` | LLM replies and datastore records | `extra="ignore"` | Required fields are still enforced, but extra keys the model invented are dropped. |

Why LLM output gets the lenient treatment: an LLM will happily add fields nobody asked
for. Rejecting a good answer because it included one extra key would be wrong. Missing a
*required* field is still a failure — a `SqlPlan` with no `sql` is useless.

### Where LLM replies are validated

All of it happens in one function, `parse_llm_json` in `src/utils/helpers.py`. This is the
single place untrusted model output becomes a typed object. In order:

1. Empty content → error.
2. Remove `<think>...</think>` blocks and ``` code fences.
3. `json.loads`. If that fails, fall back to the outermost balanced `{...}` or `[...]` in
   the text — this rescues replies where the model wrapped its JSON in prose.
4. **Reject `{}` and `[]`.**
5. `model_validate` against the schema.
6. Any failure raises `LLMResponseError`.

**Step 4 is not obvious and matters.** Every LLM schema is a `LenientModel` whose fields
have empty defaults, so `{}` validates perfectly as "all defaults" — zero entities, zero
sub-questions. The calling code cannot tell that apart from a real answer, so the failure
is completely invisible. A 30B model with reasoning reduced does return `{}` sometimes.

### What happens when validation fails

`complete_model` retries **once**, putting the validation error into the prompt so the
model can correct itself. That retry is counted as `llm_validation_failures_total` and
appears as its own `llm.<node>.retry` span. If the second attempt also fails, it raises
`LLMResponseError`, and the calling node applies its own documented fallback:

| Node | Fallback when the LLM cannot produce valid output |
|---|---|
| `decompose_query` | Use the original question as the only sub-question |
| `generate_sql` | Return "I could not find the relevant details or tables" |
| `synthesize_answer` | A generic "I found N records" summary |
| `recommend_visualizations` | No chart, table only |

So a bad LLM reply degrades the answer. It never crashes the request.

### Schemas do more than check types

- `SqlPlan.sql` — minimum length 1, and strips ```` ```sql ```` fences automatically, so no
  node has to do that by hand.
- `SubQuestions.sub_questions` — must have at least one item.
- `VisualizationSpec` — a validator enforces that `spec` is present whenever
  `is_visualizable` is true. The two fields cannot contradict each other.

### If you add a new LLM schema

Give it at least one **required** field. If every field has a default, `{}` and any other
junk reply will validate as an empty object, and the empty-payload guard above is the only
thing standing between you and a silent wrong answer.

Covered by 17 tests in `tests/test_schemas.py` and 3 in `tests/test_api_contract.py`.

## 10. Conventions you will otherwise break

- **Prompts use `string.Template` `$placeholder`, not `str.format`** — the prompts are
  full of literal JSON braces. `safe_substitute` **silently leaves unknown placeholders
  unfilled**, so a typo'd variable name produces a subtly broken prompt and no error.
  This has bitten before.
- **Pass `operation=self.name` to every LLM call.** It is what routes the reasoning
  switch and names the span. Omit it and the off-list silently matches nothing — the
  feature looks wired and does nothing. This has also bitten before.
- **Every boundary is a pydantic model** (`src/schemas/base.py`): `StrictModel` inbound
  (unknown field → 422), `ApiModel` outbound, `LenientModel` for LLM/datastore output.
  Nothing crosses a boundary as a bare dict. Note `LenientModel` means `{}` validates as
  all-defaults — `parse_llm_json` rejects empty payloads for exactly this reason.
- **Cyclomatic complexity < 10**, enforced by a test: `scripts/check_complexity.py src`.
- **No `print()`.** `get_logger(__name__)` from `src.core.logging`; every record carries
  the trace/span id.

Checks: `make test` (103 tests, ~1s, no services needed) · `cd frontend_new && npm test`
· `make smoke` (needs the full stack live).

## 11. State of the repo — read this before you commit

- Branch `feature/backend-refactor-clean`. **All of the recent work is uncommitted in the
  working tree**, including `docs/`, `Makefile`, all of `backend/scripts/`,
  `tests/test_llm.py`, and the frontend router. `git stash` or a bad checkout loses it.
  Commit before doing anything else.
- Do not touch `master` or `atique_finale_graph_visualization`.
- `docker-compose.yml.bak` and `registry.json.bak` are scratch; delete them.
- The root `README.md` of this folder predates the refactor and is wrong in specifics
  (Bedrock, `frontend/`, `app.main:app`, Hazelcast). This file supersedes it.

## 12. Security — outstanding, must be done

- `registry.json` holds **plaintext Oracle usernames and passwords**, and `.env` holds the
  NVIDIA key. Both are gitignored now, but **both exist in earlier pushed git history.**
  Untracking does not undo that. **Every credential in them needs rotating.** History
  rewriting (`git filter-repo`) has deliberately not been started — it rewrites shared
  branches and needs a coordinated decision.
- The login screen is a **role selector, not authentication.** No credential is checked.
  The admin/user split is a UI guard only; the API has no auth at all. Anything
  internet-facing needs real auth first.

## 13. Deliberately not built

- **Hazelcast is skipped.** `CacheClient.create` returns `None` on failure, so the app
  starts fine but multi-turn chat history is always empty. Single questions are
  unaffected. Re-adding the container is a four-line compose revert.
- No CI, no auth, no migrations. `registry.json` is untracked, so a fresh clone must
  re-onboard — `make smoke` doubles as that command.
- 8 GB of RAM is genuinely tight. Pressure valve, in order: stop grafana+prometheus
  (−450 MB, keeps traces), then elasticsearch (−1.1 GB; retrieval degrades to
  `GraphReadService.all_schemas()`, adequate for two small databases).

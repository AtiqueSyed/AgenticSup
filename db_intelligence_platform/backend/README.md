# DB Intelligence Platform -- Backend

FastAPI + LangGraph backend for the Enterprise Agentic Database Intelligence
Platform: onboard a database (introspect schema, build a Neo4j knowledge graph,
generate embeddings), then answer natural-language questions against it
(NL -> SQL -> validate -> synthesize answer).

## Layout

```
src/
  main.py          # create_app() factory; wires middleware, telemetry, routers
  core/
    config.py      # Settings (pydantic-settings, loaded once from .env)
    telemetry.py    # OpenTelemetry setup: providers, exporters, auto-instrumentation
    logging.py      # stdlib logging config; every line carries trace/span id
    lifespan.py      # startup/shutdown: builds and closes the client container
  clients/          # one thin wrapper per external system (Neo4j, Oracle,
                    # Elasticsearch, Hazelcast, OpenAI/LLM, embeddings), plus
                    # container.py, which holds them all as one `Clients` object
                    # built during lifespan and reached via `get_clients`
  services/         # business logic: onboarding, query, graph read/write,
                    # search, and the file-backed database registry
  routes/           # thin HTTP layer -- request in, call a service, response out
  schemas/          # pydantic DTOs for every boundary (see "Development standards")
  agents/           # the two LangGraph workflows (onboarding, query), each with
                    # its nodes, state, and prompts/*.txt
  utils/
    helpers.py      # the one shared helper module: prompt loading, LLM-output
                    # parsing, JSON helpers, and the `traced` decorator
  models/           # legacy SQLAlchemy declarative models (DatabaseConnection,
                    # TableMetadata, ColumnMetadata) -- not imported or wired into
                    # the app; the registry (`services/registry_service.py`) is
                    # the actual source of truth for onboarded databases
```

## Running it

```bash
uv sync
cp .env.example .env   # then fill in real credentials
uv run uvicorn src.main:app --reload
```

Or with Docker:

```bash
docker build -t db-intel-backend .
docker run --env-file .env -p 8000:8000 db-intel-backend
```

`/health` is mounted at the root; every other endpoint is under `/api/v1`
(see `API_PREFIX` in `src/main.py`).

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness + which LLM/Oracle/Neo4j endpoints are configured |
| GET | `/api/v1/stats` | Onboarded-database counts and entity counts |
| POST | `/api/v1/onboard` | Start the onboarding workflow for a new database (background task) |
| DELETE | `/api/v1/onboard/{database_id}` | Remove a database and its full graph/search footprint |
| GET | `/api/v1/onboard/{database_id}/status` | Poll onboarding status |
| POST | `/api/v1/query` | Ask a natural-language question against an onboarded database |
| GET | `/api/v1/graph` | Read the knowledge graph (optionally scoped to one database) |
| DELETE | `/api/v1/graph/clear` | Drop the entire graph and search index |
| POST | `/api/v1/graph/node` | Create a custom graph node |
| POST | `/api/v1/graph/edge` | Create a custom graph edge |
| DELETE | `/api/v1/graph/node/{node_id}` | Delete a node |
| DELETE | `/api/v1/graph/edge/{source_id}/{target_id}/{edge_type}` | Delete an edge |

## The two agents

Both are LangGraph `StateGraph`s built per-request/per-task by a factory
function (`build_onboarding_graph` / `build_query_graph`) so they always run
against the current `Clients`. Every node subclasses `agents/base.py:BaseNode`,
which turns each node into an OTel span and gives it a uniform error shape
(`state["status"] == "error"` short-circuits every later node).

**Onboarding** (`src/agents/onboarding/graph.py`) -- introspects a database and
builds its knowledge graph, in a straight line, no retries:

1. `extract_schema`
2. `generate_semantics`
3. `identify_entities`
4. `map_entity_columns`
5. `construct_knowledge_graph`
6. `generate_embeddings`
7. `register_metadata`

**Query** (`src/agents/query/graph.py`) -- answers a natural-language question:

1. `decompose_query`
2. `retrieve_context`
3. `generate_sql`
4. `execute_sql`
5. `validate_results` -- conditional edge: while `validation_error` is set and
   `iterations < MAX_SQL_RETRIES`, loops back to `generate_sql`; otherwise
   continues
6. `synthesize_answer`
7. `recommend_visualizations`

Prompts live as plain text at `src/agents/<agent>/prompts/<node>.txt` and are
rendered by `load_prompt(agent, name, **variables)` (in `src/utils/helpers.py`)
using `string.Template` `$placeholder` substitution -- not `str.format`, since
these prompts are full of literal JSON braces. **Editing a prompt's wording
never requires a code change**; only adding a new `$variable` does.

## Observability

OpenTelemetry is wired in `src/core/telemetry.py` and configured entirely
through env vars (see `.env.example`):

| Variable | Purpose |
|---|---|
| `OTEL_SERVICE_NAME` | Service name attached to every span/metric |
| `OTEL_SDK_DISABLED` | Skip telemetry setup entirely (used by tests/CI) |
| `OTEL_TRACES_EXPORTER` | `otlp` (real collector), `console` (print spans locally), or `none` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Collector/Jaeger gRPC endpoint, used when the exporter is `otlp` |
| `OTEL_CAPTURE_CONTENT` | Attach prompt/response bodies to spans; **off by default** |

FastAPI, SQLAlchemy, httpx (which the OpenAI SDK uses underneath), and
Elasticsearch are auto-instrumented. Everything else gets a manual span:
agent nodes (`BaseNode.__call__`), Neo4j queries (`clients/neo4j.py`, since
there's no official OTel instrumentation for the driver), and LLM calls
(`clients/llm.py`). LLM spans carry `gen_ai.*` semantic-convention attributes
(`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`,
`gen_ai.usage.output_tokens`), so per-node cost and latency are visible in the
trace.

`OTEL_CAPTURE_CONTENT` defaults to `false` because prompts carry live schema
and sample data from onboarded databases -- turn it on deliberately, and only
somewhere you're comfortable with that content landing in your tracing
backend.

To view traces locally without a collector, set `OTEL_TRACES_EXPORTER=console`
and spans print to stdout. To use a real backend, run a collector or Jaeger
and point `OTEL_EXPORTER_OTLP_ENDPOINT` at it (default:
`http://localhost:4317`).

## Development standards

- **Cyclomatic complexity stays under 10** per function/method, enforced by
  `.venv/bin/python scripts/check_complexity.py src` (backed by `radon`; the
  limit is configurable with `--max N`).
- **Run tests** with `.venv/bin/pytest`.
- **Every boundary is validated by a pydantic model** -- see `src/schemas/base.py`:
  `StrictModel` for inbound HTTP (unknown fields are a 422), `ApiModel` for
  outbound HTTP, and `LenientModel` for LLM and datastore output (required
  fields enforced, extra keys dropped). Nothing crosses a boundary as a bare
  dict.
- **No `print()`.** Use `get_logger(__name__)` from `src.core.logging` --
  every record is automatically tagged with the current trace/span id.

## Security notes

- `registry.json` holds **plaintext Oracle usernames and passwords** for every
  onboarded database and is already committed in git history. It's now
  git-ignored going forward (see `.gitignore`), but that alone doesn't remove
  it from history: run `git rm --cached registry.json` and **rotate every
  credential in it**. Its location is configurable via the `REGISTRY_PATH`
  setting if you want to move it outside the repo entirely.
- `.env` is likewise tracked in git history and should be untracked
  (`git rm --cached .env`) with its secrets rotated. Only `.env.example`
  (a template with no real values) is meant to be committed.

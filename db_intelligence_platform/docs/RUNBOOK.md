# Runbook

Bring the DB Intelligence Platform up locally, onboard the two Oracle schemas, and
prove the whole thing works end to end. Commands assume you're at the repo root
(`db_intelligence_platform/`) unless noted.

## 0. Prerequisite: raise Docker Desktop's memory

This stack is tuned to fit an 8 GB Mac, but only if Docker Desktop itself is given
enough RAM: **Docker Desktop -> Settings -> Resources -> Memory -> 6 GB**, then
Apply & Restart.

- App infra profile (`make infra` without metrics -- see below): ~4.2 GB
- With the `metrics` profile (Prometheus + Grafana): ~4.6 GB

Skipping this step is the single most common failure mode -- see
[Troubleshooting](#troubleshooting) below.

## 1. Bring up infra

```bash
make infra
```

Runs `docker compose --profile metrics up -d --wait`: oracle, neo4j, elasticsearch,
otel-collector, jaeger, prometheus, grafana. `--wait` blocks until every service's
healthcheck passes -- Oracle's first boot takes 3-5 minutes (it's initializing the
database, not just starting a process), so this step is slow the first time only.

Hazelcast and Kibana are intentionally not part of this stack. Their absence is
expected, not a regression -- see [What's missing on purpose](#whats-missing-on-purpose).

## 2. Seed Oracle

```bash
make seed
```

Runs `backend/scripts/seed_oracle.py`, which creates the `CMS` and `DAKSH` schemas and
loads the sample data (Indian banking-ombudsman complaint cases and supervisory
inspection reports).

## 3. Start the backend

```bash
make api
```

Runs `uv run uvicorn src.main:app --reload --port 8000` on the host (not in a
container -- that's why `backend/.env` points at `localhost` for Oracle/Neo4j/ES).
Use `make api-console` instead if you want OTel spans printed to stdout rather than
exported to Jaeger.

## 4. Run the smoke test

```bash
make smoke
```

Runs `backend/scripts/smoke_e2e.py` against the running API: checks `/health`, onboards
both databases, polls onboarding to completion (allow up to ~10 minutes -- onboarding
runs 7 LangGraph nodes including 3 LLM calls), checks `/stats` and `/graph`, then asks
three natural-language questions and prints the generated SQL and answer for each.
Exits non-zero on any failure.

Already onboarded and just iterating on the query side? `make smoke` re-onboards from
scratch every time, which is slow. Run the script directly with `--skip-onboard` to
reuse the databases already in `/api/v1/stats` and jump straight to the query phase:

```bash
cd backend && uv run python scripts/smoke_e2e.py --skip-onboard
```

## 5. Poke around

```bash
make ui
```

Frontend dev server at **http://localhost:5174** (Vite, proxies `/api` to
`localhost:8000`).

## URL / port reference

| Service | URL | Notes |
|---|---|---|
| Backend API | http://localhost:8000 | `/health` at root, everything else under `/api/v1` |
| Frontend | http://localhost:5174 | `npm run dev` in `frontend_new/`, proxies `/api` to the backend |
| Oracle | localhost:1521 | PDB **FREEPDB1** (not XEPDB1); users `CMS`/`cms`, `DAKSH`/`daksh` |
| Neo4j Browser | http://localhost:7474 | bolt on 7687, auth `neo4j`/`password` |
| Elasticsearch | http://localhost:9200 | security disabled, no auth needed |
| Jaeger UI | http://localhost:16686 | traces for every agent node and LLM call |
| Prometheus | http://localhost:9090 | `metrics` profile only |
| Grafana | http://localhost:3000 | `metrics` profile only, `admin`/`admin` |

## What good looks like

- `make infra` finishes with every service `healthy` (`docker compose ps` shows no
  `Exited` or `unhealthy` rows).
- `GET /health` returns `"llm_provider": "https://integrate.api.nvidia.com/v1"`.
- `POST /api/v1/onboard` for CMS and DAKSH both reach status `completed` (poll
  `GET /api/v1/onboard/{id}/status`).
- `GET /api/v1/stats` shows `"total_databases": 2` and `"entities_identified"` well
  above 0 (dozens, not a handful -- one entity per business concept the LLM found
  across both schemas).
- `GET /api/v1/graph` returns a non-empty `nodes` list you can see rendered in the
  frontend's graph view.
- `POST /api/v1/query` returns a non-null `sql_used` and an `answer` that is an actual
  sentence about the data, not the "I could not find..." fallback string.
- Jaeger shows one trace per onboarding run and per query, with `onboarding.*` /
  `query.*` spans and `gen_ai.*` attributes on the LLM ones.
- `make smoke` prints `All checks passed.` and exits 0.

## Troubleshooting

**Containers show `Exited (137)`** -- Docker was OOM-killed. This is the Docker
Desktop memory setting from [step 0](#0-prerequisite-raise-docker-desktops-memory),
not raised. Bump it to 6 GB and restart Docker Desktop, then `make infra` again.

**Onboarding or the smoke test seems to hang / Oracle connection errors early on** --
Oracle's first boot takes 3-5 minutes to initialize the database files, even though
the container may already show as "running." Watch it directly:

```bash
docker compose logs -f oracle
```

Wait for the line `DATABASE IS READY TO USE` before onboarding or seeding.

**`ORA-01017: invalid username/password`** -- wrong credentials for the connection
string. It's `CMS`/`cms` and `DAKSH`/`daksh`, matching the users created by
`infra/oracle/init/01_users.sql`.

**`ORA-12514: TNS:listener does not currently know of service requested`** -- the
connection string is using the wrong service name. This image's pluggable database is
**FREEPDB1**, not XEPDB1 (that's the older `oracle-xe` image's default). Check
`?service_name=FREEPDB1` in the connection string.

**NVIDIA `404 ... Not found for account`** -- the model id in `DEFAULT_LLM_MODEL`
isn't entitled on this API key. Verified-working ids on this account:

- `nvidia/nemotron-3-super-120b-a12b`
- `nvidia/nemotron-3-ultra-550b-a55b`
- `nvidia/nemotron-3.5-lightning-30b-a3b`

The `llama-3.1-nemotron-*` ids all 404 on this account -- don't use them. Before
switching to `lightning-30b` because it's the smallest, read
[`docs/MODELS.md`](MODELS.md) -- on this account it is measurably slower, not faster.

**NVIDIA `503 ResourceExhausted`** -- the free-tier rate limit was hit. Wait and
retry; onboarding and query both make LLM calls, so this can surface at any node.

**`/api/v1/stats` shows the database but `entities_identified` is 0** -- onboarding
started but failed partway through (most likely `construct_knowledge_graph` or an
earlier LLM node). Check the status string:

```bash
curl http://localhost:8000/api/v1/onboard/<database_id>/status
```

A status of `error` means a node's exception was caught and the graph short-circuited;
`failed: ...` means the graph itself raised. Either way, check the Jaeger trace for
that `database_id` (filter by the `db.id` span attribute) to see which node actually
failed and why.

**A query returns "I could not find the relevant details or tables to answer this
question."** -- the knowledge graph has nothing to retrieve against for that question,
i.e. onboarding never populated it (or you're asking before onboarding finished).
Re-onboard, or check `/api/v1/stats` for `entities_identified` first.

**Memory pressure** -- if the Mac is struggling to keep the stack up, relieve pressure
in this order:

1. Drop the `metrics` profile: run `docker compose up -d --wait` (no `--profile
   metrics`) instead of `make infra` -- saves ~450 MB by not starting
   Prometheus/Grafana.
2. Stop Elasticsearch: `docker compose stop elasticsearch` -- saves ~1.1 GB.
   `SearchService` no-ops whenever `clients.elastic` is `None`, so entity vector search
   silently returns no matches and `ContextRetriever.resolve()` falls back to
   `GraphReadService.all_schemas()` -- every table's schema is still visible to the
   query agent, which is plenty for two small onboarded databases.

## Swapping the LLM

There is no provider-abstraction layer. The backend is configured entirely by
`OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `DEFAULT_LLM_MODEL` in `backend/.env` --
swapping provider or model is a three-line `.env` edit, not a code change.

Before changing `DEFAULT_LLM_MODEL`, read [`docs/MODELS.md`](MODELS.md). In short:

- Of the 81 models this NVIDIA NIM key lists, only 3 are actually entitled (the ones
  in the troubleshooting entry above) -- everything else 404s.
- The smallest entitled model (`lightning-30b`) is ~5x *slower* than the default
  (`super-120b`) because it emits far more chain-of-thought tokens by default.
  Model size does not predict latency here; reasoning-token volume does.
- Reasoning is a switch, not a slider, on this endpoint: `chat_template_kwargs:
  {"thinking": "off"}` actually disables it; a plausible-looking `budget_tokens`
  parameter is accepted with HTTP 200 and silently does nothing.
- After any model swap, re-run `make smoke` -- a model swap changes SQL generation
  quality, not just latency.

## What's missing on purpose

- **Hazelcast** was deliberately removed from the stack. `CacheClient.create` fails
  after a 2-second connection timeout and returns `None` -- expect a ~2s startup delay
  and one logged connection exception on backend boot. Nothing else breaks, but
  **multi-turn chat history is disabled**: `QueryService.ask` only appends to history
  when `clients.cache` is truthy, so every query is answered independently of prior
  turns.
- **Kibana** was deliberately removed. Use the Elasticsearch REST API directly
  (`curl localhost:9200/...`) or Neo4j Browser / the frontend's graph view instead.

# Telemetry

This app exports OpenTelemetry traces and metrics from `setup_telemetry()` in
`backend/src/core/telemetry.py`. This doc assumes you have never opened Jaeger
before.

## Bringing the stack up

The backend runs on the host (`uv run uvicorn src.main:app`), not in a
container -- only the observability backends are containerised.

```bash
docker compose --profile metrics up -d --wait
```

(`--profile metrics` also brings up the base stack `docker compose up -d`
depends on -- Oracle, Neo4j, Elasticsearch, the collector, Jaeger -- plus
Prometheus and Grafana. Leave off `--profile metrics` if you only want traces
and don't need Prometheus/Grafana.)

| Tool | URL | What it's for |
|---|---|---|
| Jaeger | http://localhost:16686 | Browse and search traces |
| Prometheus | http://localhost:9090 | Query raw metrics, run PromQL |
| Grafana | http://localhost:3000 | Dashboards over the Prometheus datasource (anonymous admin access, no login needed) |

The backend's default `OTEL_EXPORTER_OTLP_ENDPOINT` (`backend/src/core/config.py:58`)
is `http://localhost:4317`, which the collector container publishes on the
host, so no `.env` changes are needed for this to work.

## Three ways to view traces

1. **Jaeger UI** (above) -- the normal path. Requires the collector + Jaeger
   containers to be up.
2. **Console exporter** -- no containers at all:
   ```bash
   OTEL_TRACES_EXPORTER=console uv run uvicorn src.main:app
   ```
   Spans print as JSON to stdout as they end. Useful for a quick look at one
   request without standing up the stack (`_build_span_processor` in
   `backend/src/core/telemetry.py:46-54` is what switches exporters on this
   env var).
3. **`OTEL_SDK_DISABLED=true`** -- turns tracing and metrics off entirely.
   `setup_telemetry()` returns immediately (`backend/src/core/telemetry.py:88-91`).
   This is what the test suite uses (see `backend/tests/conftest.py`), so tests
   don't need a collector running and don't pay span-creation overhead.

## Span tree: `POST /api/v1/query`

One request is one trace. The route (`backend/src/routes/query.py:15-24`) is
synchronous end to end, so every node in the LangGraph
(`backend/src/agents/query/graph.py:36-67`) nests under the request's
FastAPI-instrumented root span.

Every agent node gets its span from `BaseNode.__call__`
(`backend/src/agents/base.py:60`), named `f"{agent}.{name}"` -- here
`agent = "query"` (`backend/src/agents/query/nodes.py`, set per class). Every
LLM call gets its span from `LLMClient._chat`
(`backend/src/clients/llm.py:98`), named `f"llm.{operation}"`. Every call site
passes `operation=self.name`, so an LLM span is named after the node that
issued it (`llm.generate_sql`, `llm.identify_entities`, ...), and a retry after
a failed schema validation is `llm.<node>.retry`
(`backend/src/clients/llm.py:88`). That same `operation` value is what the
per-node reasoning switch keys off (`LLM_REASONING_OFF_OPERATIONS`), and the
mode actually used is on the span as `gen_ai.reasoning`.

```
POST /api/v1/query                                (FastAPIInstrumentor root span)
├─ query.decompose_query                          nodes.py:30  DecomposeQueryNode
│  └─ llm.decompose_query                         LLM splits the question into sub-questions (SubQuestions)
│     └─ llm.decompose_query.retry                only if the first reply failed schema validation
├─ query.retrieve_context                         nodes.py:48  RetrieveContextNode
│  ├─ embeddings.embed  (x1 per sub-question)     embeddings.py:41, via SearchService.match_entity_ids
│  ├─ Elasticsearch client span(s)                ElasticsearchInstrumentor auto-span, the kNN search
│  └─ neo4j.schemas_for_entities                  graph_read.py:158, or neo4j.all_schemas (graph_read.py:166)
│                                                 as the fallback when nothing matched (context_retriever.py:28-33)
├─ query.generate_sql                             nodes.py:79  GenerateSqlNode
│  └─ llm.generate_sql                            LLM writes the SQL (SqlPlan)
├─ query.execute_sql                              nodes.py:113 ExecuteSqlNode
│  └─ SQLAlchemy client span                      SQLAlchemyInstrumentor auto-span, the Oracle SELECT
├─ query.validate_results                         nodes.py:144 ValidateResultsNode (no children -- bumps `iterations`)
│
│  ── conditional edge (graph.py:24-33): while validation_error is set and
│     iterations < MAX_SQL_RETRIES (default 3, config.py:49), loop back to
│     generate_sql. A repeated generate_sql -> execute_sql -> validate_results
│     block in the trace is that retry loop firing. ──
│
├─ query.synthesize_answer                        nodes.py:154 SynthesizeAnswerNode (runs even if an earlier node errored: skip_on_error=False)
│  └─ llm.synthesize_answer                       LLM writes the natural-language answer
└─ query.recommend_visualizations                 nodes.py:189 RecommendVisualizationsNode
   └─ llm.recommend_visualizations                LLM picks a chart type/spec (VisualizationSpec), skipped if no query_results
```

## Span tree: `POST /api/v1/onboard`

`onboard_database` (`backend/src/routes/onboarding.py:23-38`) registers the
database and hands `OnboardingService.run` to FastAPI's `BackgroundTasks`,
then returns `202`-shaped JSON immediately. **The 7-node onboarding graph runs
after the response has already been sent, in a task with no active request
context -- it lands as its own separate trace, not nested under the `POST
/api/v1/onboard` span.** This surprises people who go looking for onboarding
spans under the request that kicked it off and find only a tiny root span
there.

```
POST /api/v1/onboard                              (short-lived: registers the DB, schedules the background task, returns)

--- separate trace, starts once the background task runs ---

onboarding.extract_schema                         onboarding/nodes.py:23  ExtractSchemaNode
└─ SQLAlchemy client span(s)                      schema introspection queries against the target Oracle DB
onboarding.generate_semantics                     onboarding/nodes.py:40  GenerateSemanticsNode
└─ llm.generate_semantics                         table/column descriptions (TableSemantics)
onboarding.identify_entities                      onboarding/nodes.py:56  IdentifyEntitiesNode
├─ neo4j.existing_entities                        nodes.py:82-84, only if clients.neo4j is configured
└─ llm.identify_entities                          entities + relationships (EntityExtraction)
onboarding.map_entity_columns                     onboarding/nodes.py:111 MapEntityColumnsNode
└─ llm.map_entity_columns                         entity key columns (EntityKeyMap)
onboarding.construct_knowledge_graph              onboarding/nodes.py:139 ConstructKnowledgeGraphNode
├─ neo4j.merge_database                           graph_write.py:65
├─ neo4j.merge_tables                             graph_write.py:85
├─ neo4j.merge_columns                            (x1 per table)           graph_write.py:108, looped in nodes.py:164-165
├─ neo4j.merge_entities                           graph_write.py:124
├─ neo4j.merge_entity_keys                        (x1 per entity)       graph_write.py:141, looped in nodes.py:167-168
└─ neo4j.merge_relationships                      graph_write.py:191
onboarding.generate_embeddings                    onboarding/nodes.py:175 GenerateEmbeddingsNode
├─ embeddings.embed                               (x1 per entity)               embeddings.py:41, via SearchService.index_entities
└─ Elasticsearch client span(s)                   ElasticsearchInstrumentor auto-span, indexing each document
onboarding.register_metadata                      onboarding/nodes.py:200 RegisterMetadataNode (no-op, no children)
```

Poll `GET /api/v1/onboard/{database_id}/status` to watch progress -- it reads
`DatabaseRegistry`, not the trace.

## What to actually look for

- **Cost and latency per node**: every `llm.*` span carries
  `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens`
  (`backend/src/core/telemetry.py:34-35`, set in `_record_usage`,
  `backend/src/clients/llm.py:194-200`) plus `gen_ai.request.model` and
  `gen_ai.system`. Sum these across a trace's `llm.*` spans to see where a
  request's tokens (and therefore cost) actually went.
- **The SQL retry loop firing**: a second `query.generate_sql` ->
  `query.execute_sql` -> `query.validate_results` sequence in one trace means
  the first SQL attempt failed validation and the conditional edge sent it
  back (`backend/src/agents/query/graph.py:24-33`).
- **Node failures**: a successful node span gets the attribute
  `agent.node.status = "ok"` (`backend/src/agents/base.py:67`) -- set *only*
  on the success path. A failed node's span never gets that attribute;
  instead `record_exception` (`backend/src/utils/helpers.py:170-173`) marks
  the span's OTel status `ERROR` and records the exception as a span event.
  So: filter Jaeger for error-status spans (or spans missing
  `agent.node.status`) to find failures, don't look for a `status=error`
  attribute value -- one is never written.

## Metrics

The Python SDK's metric names are dot-separated; the collector's Prometheus
exporter renders them Prometheus-compliant on scrape (verified against
`pkg/translator/prometheus` in `opentelemetry-collector-contrib`, the same
version pinned in `docker-compose.yml`): dots become underscores, a
monotonic-sum (counter) instrument gets a `_total` suffix, and a unit gets
appended and translated to its long form (`ms` -> `milliseconds`) before the
standard Prometheus histogram suffixes (`_bucket`, `_sum`, `_count`) are
added.

| SDK name (source) | Prometheus name(s) | What it means | PromQL |
|---|---|---|---|
| `llm.calls` counter, no unit (`backend/src/clients/llm.py:29`) | `llm_calls_total` | One per completed chat-completion call, labeled `operation` -- the node name (`generate_sql`, `identify_entities`, ...), or `<node>.retry` for a retry after a schema failure (`backend/src/clients/llm.py:115`) | `sum(rate(llm_calls_total[5m])) by (operation)` |
| `llm.validation_failures` counter, no unit (`backend/src/clients/llm.py:30`) | `llm_validation_failures_total` | Incremented when a structured reply fails schema validation on the first try, labeled `operation` and `model` (the Pydantic model name) (`backend/src/clients/llm.py:85`) | `sum(rate(llm_validation_failures_total[5m])) by (model)` |
| `agent.node.duration` histogram, unit `ms` (`backend/src/agents/base.py:23-25`) | `agent_node_duration_milliseconds_bucket` / `_sum` / `_count` | Wall-clock time of one agent node run, labeled `agent.name`, `agent.node`, and `outcome` (`ok`/`error`). Recorded in a `finally` block (`backend/src/agents/base.py:74-77`), so a node that fails after 30s is timed too | p95: `histogram_quantile(0.95, sum(rate(agent_node_duration_milliseconds_bucket[5m])) by (le))` |

Attribute-to-label sanitization follows the same rule (dots -> underscores),
so span/metric attributes with dots (e.g. `agent.name`) would surface as
`agent_name` labels if they were attached to a metric -- but as noted above,
today the histogram is never recorded, so no labels reach Prometheus for it
in practice.

## Attribute-to-label note

Attribute names with dots are sanitized the same way (dots -> underscores), so the
histogram's `agent.name` / `agent.node` attributes reach Prometheus as `agent_name` and
`agent_node` labels.

## Capturing prompts and completions

Set `OTEL_CAPTURE_CONTENT=true` (`backend/src/core/config.py:65`) to attach
the full prompt and completion text as span events (`gen_ai.prompt` /
`gen_ai.completion`, `backend/src/clients/llm.py:101,119`) on every
`llm.*` span. It is **off by default** because those prompts embed the
retrieved database schema and sampled row values (see
`SAMPLE_ROW_LIMIT`/`RESULT_ROW_LIMIT` in
`backend/src/agents/query/nodes.py:26-27` and the `context_str`/`results_str`
built into the `generate_sql`/`synthesize_answer` prompts) -- i.e. real
customer data from the target database, not just the user's question. Only
turn it on against non-production data, and expect it to substantially
increase span size sent to the collector.

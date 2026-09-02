# API Reference

Base: `http://localhost:8000`. Everything except `/health` is under `/api/v1`.
CORS is `allow_origins=["*"]` (`src/main.py`) — tighten before production.

All bodies are JSON. Request models set `extra="forbid"`: an unknown field is a
**422**, not a silent ignore. Validation errors are FastAPI's standard
`{"detail": [...]}` 422 shape.

---

## `GET /health`

Liveness plus which external endpoints this process is configured against. Reads
settings only — does **not** dial Neo4j, Oracle, or Elasticsearch, so a 200 here
does not mean the dependencies are up.

```json
{"status":"ok","llm_provider":"https://…/v1","oracle_host":"host.docker.internal","neo4j_uri":"bolt://localhost:7687"}
```

Not called by the frontend.

---

## `GET /api/v1/stats`

Registry counts for the admin dashboard. Reads `registry.json` and one Neo4j
`count(:Entity)`.

**Response**

| Field | Type | Notes |
|---|---|---|
| `total_databases` | int | Registry entry count |
| `database_names` | string[] | Names only, in registry order |
| `databases` | `{id,name,status}[]` | `status` defaults to `"completed"` when the entry has never been through onboarding |
| `entities_identified` | int | `MATCH (n:Entity) RETURN count(n)` |
| `queries_today` | int | **Always `0`** — never incremented anywhere |

A Neo4j failure does not fail the request: `entities_identified` falls back to
`0` and the error is logged (`src/routes/stats.py:_count_entities`).

---

## `POST /api/v1/onboard`

Registers a database and kicks off the onboarding LangGraph as a FastAPI
`BackgroundTask`. **Returns immediately** — poll the status endpoint for progress.

**Request**

| Field | Type | Rules |
|---|---|---|
| `database_name` | str | `min_length=1` |
| `connection_string` | str | must match `^[A-Za-z][A-Za-z0-9+_.-]*://` |

**Response** `{"message":"Onboarding started","database_id":"<md5>"}`

`database_id` is `md5(connection_string)` — deterministic, so re-onboarding the
same connection string reuses the same id. Before the background task starts,
`start()` wipes that id's prior Neo4j and Elasticsearch footprint, so
re-onboarding replaces rather than duplicates.

Background pipeline (`src/agents/onboarding/graph.py`), straight line, no retries:
`extract_schema → generate_semantics → identify_entities → map_entity_columns →
construct_knowledge_graph → generate_embeddings → register_metadata`.

---

## `GET /api/v1/onboard/{database_id}/status`

**Response** `{"database_id":"…","status":"…"}`

| `status` | Meaning |
|---|---|
| `unknown` | Unregistered id, or registered but the background task has not started |
| `running` | Pipeline in flight |
| `completed` | Finished |
| `failed: <exception>` | Pipeline raised |

Status is persisted in `registry.json`, so it survives a process reload.
Intermediate node names (`extracted_schema`, `identified_entities`, …) are written
to the state but only the terminal value reaches the registry — polling never
observes a mid-pipeline stage.

---

## `DELETE /api/v1/onboard/{database_id}`

Removes a database and its full footprint: Neo4j subgraph, both Elasticsearch
indices' documents for that id, and the registry entry.

**Response** `{"status":"deleted","database_id":"…"}`

Always **200**, including for an id that was never registered. Neo4j and
Elasticsearch failures are logged and swallowed; the registry entry is removed
regardless. Deleting a live database is not blocked.

---

## `POST /api/v1/query`

The full NL→SQL→execute→validate→synthesize workflow, run synchronously.

**Request**

| Field | Type | Rules |
|---|---|---|
| `question` | str | `min_length=1`, `max_length=2000` |
| `database_id` | str \| null | `null` = let the agent route across every onboarded database. The literal `"selected-db-id"` is treated as `null` |

**Response** — all six keys are always present; the nullable ones are emitted as
`null` rather than omitted.

| Field | Type |
|---|---|
| `answer` | str (`"Error synthesizing answer"` on failure) |
| `database_id` / `database_name` | str \| null — which database the agent actually routed to |
| `sql_used` | str \| null |
| `results` | `object[]` \| null — raw rows |
| `visualizations` | object \| null — `{is_visualizable, spec?}` |

Pipeline: `decompose_query → retrieve_context → generate_sql → execute_sql →
validate_results → synthesize_answer → recommend_visualizations`. `validate_results`
is a conditional edge: while a validation error is set and
`iterations < MAX_SQL_RETRIES`, it loops back to `generate_sql`.

Chat history is kept per session in Hazelcast under `chat_{database_id}` (or
`chat_global` when `database_id` is null) and fed back in as context. No cache
configured means no history, not an error.

Any unhandled exception becomes a **500** with the exception string in `detail`.

---

## `GET /api/v1/graph`

The knowledge graph, pre-shaped for React Flow.

**Query param** `database_id` (optional) — scopes to one database. Omit for the
whole graph.

**Response**

```json
{"nodes":[{"id":"…","type":"input|default","data":{"label":"[Table]\nORDERS"},"position":{"x":0,"y":0}}],
 "edges":[{"id":"src-tgt-TYPE","source":"…","target":"…","label":"HAS_TABLE","animated":true}]}
```

- `node.type` is `"input"` for `:Database`, `"default"` for everything else.
- `node.data.label` is `"[<Neo4jLabel>]\n<name>"`. The frontend parses the node's
  kind back out of this string — it is the only place the type survives.
- All positions are `{x:0,y:0}`; the frontend does its own layout.
- `edge.label` is the relationship type. `edge.animated` is `label != "CONTAINS"`.
- **There is no `edge.type` field.**

**500** if Neo4j is unreachable — this endpoint has no fallback.

---

## `POST /api/v1/graph/node`

Manual node creation from the graph editor. `MERGE`s by `id`.

| Field | Type | Rules |
|---|---|---|
| `id` | str | `min_length=1` |
| `name` | str | `min_length=1` |
| `type` | enum | **exactly** `Database` \| `Table` \| `Column` \| `Entity` — anything else is a 422 |
| `description` | str | optional, defaults `""` |

**Response** `{"status":"created","node_id":"…"}`

`type` is interpolated into the Cypher label, which is why it is a closed enum
rather than a free string.

---

## `POST /api/v1/graph/edge`

Manual relationship creation. `MERGE`s by `(source)-[type]->(target)`.

| Field | Type | Rules |
|---|---|---|
| `source` / `target` | str | `min_length=1`, and both must already exist |
| `type` | str | must match `^[A-Z_][A-Z0-9_]*$` (uppercase, underscores, no leading digit) |

**Response** `{"status":"created","source":"…","target":"…"}`

**404** `source and target must both be existing nodes`. Both endpoints are
`MATCH`ed and never merged, so an unknown id makes the whole statement match
nothing and the `MERGE` never runs — no stub node is created, and nothing is
written.

---

## `DELETE /api/v1/graph/node/{node_id}`

`DETACH DELETE` — removes the node and every relationship attached to it.
**Response** `{"status":"deleted","node_id":"…"}`. Deleting a non-existent node is
still a 200.

## `DELETE /api/v1/graph/edge/{source_id}/{target_id}/{edge_type}`

Deletes one specific relationship. **Response** `{"status":"deleted"}` — this one
carries no other keys.

`edge_type` is a path segment, so a type containing `/` cannot be addressed. All
types actually produced by the pipeline (`HAS_TABLE`, `HAS_COLUMN`, `CONTAINS`,
`MAPS_TO`, `REPRESENTS`) are safe.

## `DELETE /api/v1/graph/clear`

**Destructive, no confirmation, no scoping.** Drops every node in Neo4j, every
document in the entity index, and **empties `registry.json`** — every onboarded
database is deregistered, not just unlinked from the graph. There is no undo.

**Response** `{"status":"graph cleared"}` — always 200, even if Neo4j and
Elasticsearch both failed, since both are wrapped in try/except. A 200 here is
not evidence the graph was actually cleared.

---

# Frontend call map

Every `fetch` in `frontend_new/src`, and the endpoint it hits. Vite proxies
`/api` → `http://localhost:8000` (`vite.config.js`), so the frontend uses
relative paths and there is no base-URL config.

| Caller | Endpoint |
|---|---|
| `ChatInterface.jsx:209` | `GET /stats` — populates the database picker from `data.databases` |
| `ChatInterface.jsx:284` | `POST /query` — sends `{database_id: null, question}` |
| `ACEOnboarding.jsx:221` | `POST /onboard` |
| `ACEOnboarding.jsx:248` | `GET /onboard/{id}/status` — 2s interval |
| `ACEOnboarding.jsx:170` | `GET /graph[?database_id=]` |
| `MetadataRegistry.jsx:367` | `GET /graph` |
| `MetadataRegistry.jsx:269` | `POST /graph/node` |
| `MetadataRegistry.jsx:307` | `POST /graph/edge` |
| `MetadataRegistry.jsx:343` | `DELETE /graph/node/{id}` |
| `MetadataRegistry.jsx:349` | `DELETE /graph/edge/{src}/{tgt}/{type}` |
| `MetadataRegistry.jsx:954` | `GET /stats` |
| `MetadataRegistry.jsx:969` | `DELETE /onboard/{id}` |
| `MetadataRegistry.jsx:996` | `DELETE /graph/clear` |

Verified by replaying each call site's exact path and body against a live
backend: **12/12 endpoints reached, no 404, no 422.** `/health` is the only
endpoint the frontend never calls.

Payload checks:

- Node `type` is drag-sourced from exactly `Database`/`Table`/`Column`/`Entity`
  (`MetadataRegistry.jsx:713-737`) — all four in the backend enum.
- Edge `type` comes from a fixed `<select>` of `RELATES_TO`, `CONTAINS`,
  `HAS_TABLE`, `HAS_COLUMN`, `MAPS_TO` — all match the backend regex. Free text
  is not possible.
- Edge deletion sends `edge.label` as the type, which is what `GET /graph` puts
  there. Round-trips correctly.
- Status polling matches `running` / `completed` / `failed*` — the exact strings
  the registry writes.
- Unstructured mode posts `nosqlUrl` (default `http://localhost:9200`) as
  `connection_string`; `http://` satisfies the driver-prefix validator.

## Fixed

**1. `ACEOnboarding.jsx` animated every edge.** It mapped
`animated: e.type !== 'CONTAINS'`, but `GET /graph` edges carry `label`, not
`type`, so the comparison was `undefined !== 'CONTAINS'` — always true. The spread
had already carried the backend's correct `animated`; the override is now deleted
so `CONTAINS` renders static again, matching `MetadataRegistry.jsx`.

**2. Empty onboarding form hit the network.** `dbName` and `connUrl` both start
`''` and both are `min_length=1` server-side, so an empty submit was a 422 shown
as a generic "rejected by endpoint". `canStartPipeline` now gates both the button
and `handleStartPipeline`.

**3. `POST /graph/edge` reported a write it never made.** With both endpoints
`MATCH`ed, an unknown id matches nothing and the `MERGE` is skipped — but the
route returned `{"status":"created"}` regardless, leaving the editor drawing an
edge Neo4j did not have. `upsert_edge` now returns whether the statement wrote,
and the route raises **404** when it did not. Regression test:
`tests/test_api_contract.py::test_create_edge_404s_when_an_endpoint_is_missing`.

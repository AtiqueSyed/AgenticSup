# Enterprise Agentic Database Intelligence Platform

Onboard an Oracle database, then query it in natural language. FastAPI + LangGraph
backend, React frontend, Neo4j knowledge graph, Elasticsearch vector search, NVIDIA
Nemotron LLMs, OpenTelemetry throughout.

## Start here

**[HANDOVER.md](HANDOVER.md)** — layout, bring-up, configuration, conventions, and the
things that will bite you. Read it first.

Then, for the task at hand:

| Doc | For |
|---|---|
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | running it, and troubleshooting |
| [docs/TELEMETRY.md](docs/TELEMETRY.md) | traces, spans, metrics |
| [docs/MODELS.md](docs/MODELS.md) | swapping or tuning the LLM |
| [backend/API.md](backend/API.md) | the HTTP API |
| [backend/README.md](backend/README.md) | backend internals and coding standards |

## Quick start

```bash
# Docker Desktop -> Resources -> Memory = 6 GB first, or containers get OOM-killed.
cp backend/.env.example backend/.env    # fill in real values
make infra && make seed && make api     # then, in another shell:
make smoke && make ui                   # UI at http://localhost:5174
```

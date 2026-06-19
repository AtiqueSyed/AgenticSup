# Enterprise Agentic Database Intelligence Platform

A production-ready full-stack application that enables enterprises to onboard any structured or unstructured database and query it using natural language.

## Architecture

- **Frontend**: React, Vite, Tailwind CSS, ShadCN UI, React Flow (Knowledge Graph), ECharts (Visualizations).
- **Backend**: FastAPI, SQLAlchemy Async, LangGraph (Agentic Workflows).
- **LLMs**: AWS Bedrock (OpenAI compatible proxy used).
- **Infrastructure**: Oracle DB (Target & Registry), Neo4j (Knowledge Graph), Elasticsearch (Vector Search), Hazelcast (Caching).

## Workflows

1. **Admin Onboarding (Offline)**: Introspects database schema, generates semantic descriptions, identifies entities/relationships, pushes to Neo4j and Elasticsearch.
2. **User Query**: Natural language intent parsing, context retrieval from Neo4j/Elasticsearch, optimized SQL generation, secure execution, result synthesis, and dynamic chart recommendation.

## Setup Instructions

### Environment Setup

1. Configure the `.env` file located at `backend/.env` with your specific credentials:
   - AWS Bedrock API Keys
   - Oracle DB Credentials
   - Neo4j Credentials
   - Hazelcast Host/Port
   - Elasticsearch Host/Credentials

### Running with Docker

This project is fully dockerized for easy deployment to your VM environments.

```bash
docker-compose up -d --build
```

- **Frontend**: Available at `http://localhost:80`
- **Backend API**: Available at `http://localhost:8000/api/v1`
- **API Docs**: Available at `http://localhost:8000/docs`

### Running Locally (Development)

**Backend:**
```bash
cd backend
uv sync # Ensure dependencies are installed
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

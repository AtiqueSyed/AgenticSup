from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

app = FastAPI(
    title="Enterprise Agentic Database Intelligence Platform API",
    description="Backend API for managing databases, executing natural language queries, and interacting with the knowledge graph.",
    version="1.0.0"
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Update this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.endpoints import router as api_router

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "llm_provider": settings.OPENAI_BASE_URL,
        "oracle_host": settings.ORACLE_HOST,
        "neo4j_uri": settings.NEO4J_URI
    }

app.include_router(api_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

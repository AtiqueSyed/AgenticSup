from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
import uuid
from typing import Dict, Any

from app.agents.admin_onboarding import admin_onboarding_app
from app.agents.user_query import user_query_app

router = APIRouter()

class OnboardRequest(BaseModel):
    connection_string: str
    database_name: str

class QueryRequest(BaseModel):
    database_id: str
    question: str

# In-memory mock tracking for background tasks during hackathon
tasks_status = {}

@router.get("/stats")
async def get_stats():
    return {
        "total_databases": len(tasks_status),
        "entities_identified": len(tasks_status) * 7, # Mock entities per DB
        "queries_today": 0
    }

@router.post("/onboard")
async def onboard_database(request: OnboardRequest, background_tasks: BackgroundTasks):
    """
    Kicks off the offline Admin Onboarding workflow using LangGraph.
    This will introspect the schema, build the Neo4j graph, and generate embeddings.
    """
    db_id = str(uuid.uuid4())
    
    async def run_onboarding():
        tasks_status[db_id] = "running"
        try:
            # We would invoke the graph here
            initial_state = {
                "database_id": db_id,
                "connection_string": request.connection_string,
                "extracted_schema": {},
                "semantic_descriptions": {},
                "entities": [],
                "relationships": [],
                "status": "started",
                "errors": []
            }
            # For hackathon/sync execution we could await it, but here it's fire-and-forget
            final_state = await admin_onboarding_app.ainvoke(initial_state)
            tasks_status[db_id] = final_state.get("status", "completed")
        except Exception as e:
            tasks_status[db_id] = f"failed: {str(e)}"

    background_tasks.add_task(run_onboarding)
    
    return {"message": "Onboarding started", "database_id": db_id}

@router.get("/onboard/{database_id}/status")
async def get_onboarding_status(database_id: str):
    return {"database_id": database_id, "status": tasks_status.get(database_id, "unknown")}


@router.post("/query")
async def ask_question(request: QueryRequest):
    """
    Executes the User Query workflow: NL -> SQL -> Validate -> Synthesize Answer.
    """
    initial_state = {
        "question": request.question,
        "database_id": request.database_id,
        "relevant_context": {},
        "generated_sql": None,
        "query_results": None,
        "validation_error": None,
        "synthesized_answer": None,
        "recommended_visualizations": None,
        "iterations": 0
    }
    
    try:
        final_state = await user_query_app.ainvoke(initial_state)
        return {
            "sql": final_state.get("generated_sql"),
            "answer": final_state.get("synthesized_answer"),
            "chart": final_state.get("recommended_visualizations"),
            "results": final_state.get("query_results")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

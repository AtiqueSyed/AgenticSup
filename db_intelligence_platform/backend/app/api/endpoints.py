from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
import uuid
from typing import Dict, Any
import json
from app.core.database import hz_client

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
mock_db_connections = {}

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
    mock_db_connections[db_id] = request.connection_string
    
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
    # Grab the connection string from memory
    # Since the UI currently hardcodes "selected-db-id", we will just use the last onboarded db!
    conn_str = mock_db_connections.get(request.database_id)
    if not conn_str and mock_db_connections:
        conn_str = list(mock_db_connections.values())[-1]
    elif not conn_str:
        # Fallback to local Oracle (using host.docker.internal to reach Windows host from inside Docker container)
        conn_str = "oracle+oracledb_async://agenticsupervisor_developer:agenticsupervisor@host.docker.internal:1521/?service_name=XEPDB1"

    # Hazelcast Chat Session Caching
    chat_history = []
    session_id = f"chat_{request.database_id}"
    if hz_client:
        try:
            chat_map = hz_client.get_map("chat_sessions").blocking()
            history_str = chat_map.get(session_id)
            if history_str:
                chat_history = json.loads(history_str)
        except Exception as e:
            print(f"Hazelcast Read Error: {e}")
        
    initial_state = {
        "question": request.question,
        "database_id": request.database_id,
        "relevant_context": {"connection_string": conn_str, "chat_history": chat_history},
        "generated_sql": None,
        "query_results": None,
        "validation_error": None,
        "synthesized_answer": None,
        "recommended_visualizations": None,
        "iterations": 0
    }
    
    try:
        # We await the workflow invocation
        final_state = await user_query_app.ainvoke(initial_state)
        
        # Cache the new history back to Hazelcast
        if hz_client:
            try:
                chat_map = hz_client.get_map("chat_sessions").blocking()
                chat_history.append({"q": request.question, "a": final_state.get("synthesized_answer", "")})
                chat_map.put(session_id, json.dumps(chat_history))
            except Exception as e:
                print(f"Hazelcast Write Error: {e}")

        return {
            "answer": final_state.get("synthesized_answer", "Error synthesizing answer"),
            "sql_used": final_state.get("generated_sql"),
            "visualizations": final_state.get("recommended_visualizations"),
            "results": final_state.get("query_results")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

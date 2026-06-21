from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
import uuid
from typing import Dict, Any
import json
from app.core.database import hz_client, ORACLE_URL

from app.agents.admin_onboarding import admin_onboarding_app
from app.agents.user_query import user_query_app

router = APIRouter()

class OnboardRequest(BaseModel):
    connection_string: str
    database_name: str

from typing import Optional

class QueryRequest(BaseModel):
    database_id: Optional[str] = None
    question: str

# In-memory mock tracking for background tasks during hackathon
tasks_status = {}
mock_db_connections = {}

from app.core.database import neo4j_driver

import json
import os

REGISTRY_FILE = "registry.json"

def read_registry():
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def write_registry(data):
    try:
        with open(REGISTRY_FILE, "w") as f:
            json.dump(data, f)
    except:
        pass

@router.get("/stats")
async def get_stats():
    entities_count = 0
    if neo4j_driver:
        try:
            async with neo4j_driver.session() as session:
                res = await session.run("MATCH (n:Entity) RETURN count(n) AS c")
                record = await res.single()
                if record:
                    entities_count = record["c"]
        except Exception:
            pass
            
    db_count = 0
    db_names = []
    
    # Retrieve stats securely from the file registry
    registry = read_registry()
    db_names = [info.get("name", "Unknown DB") for info in registry.values()]
    databases = [
        {
            "id": db_id,
            "name": info.get("name", "Unknown DB"),
            "status": tasks_status.get(db_id, "completed")
        }
        for db_id, info in registry.items()
    ]
    db_count = len(db_names)
            
    if db_count == 0:
        db_count = len(tasks_status)
            
    return {
        "total_databases": db_count,
        "database_names": db_names,
        "databases": databases,
        "entities_identified": entities_count,
        "queries_today": 0
    }

import hashlib
from app.core.database import neo4j_driver, es_client
from app.core.config import settings

@router.post("/onboard")
async def onboard_database(request: OnboardRequest, background_tasks: BackgroundTasks):
    """
    Kicks off the offline Admin Onboarding workflow using LangGraph.
    This will introspect the schema, build the Neo4j graph, and generate embeddings.
    """
    # Deterministic ID to prevent duplicate DB onboardings
    db_id = hashlib.md5(request.connection_string.encode()).hexdigest()
    mock_db_connections[db_id] = request.connection_string
    
    # Store metadata securely in file registry
    registry = read_registry()
    registry[db_id] = {
        "name": request.database_name,
        "connection_string": request.connection_string
    }
    write_registry(registry)
    
    # Proactively wipe previous footprint to prevent entity duplication
    if neo4j_driver:
        try:
            async with neo4j_driver.session() as session:
                # Delete Database node and all entities uniquely tied to it
                await session.run("MATCH (db:Database {id: $db_id})-[:CONTAINS]->(e:Entity) DETACH DELETE db, e", db_id=db_id)
        except Exception as e:
            print(f"Cleanup Neo4j Error: {e}")
            
    if es_client:
        try:
            await es_client.delete_by_query(
                index=f"{settings.ELASTICSEARCH_INDEX_PREFIX}tables",
                query={"match": {"database_id": db_id}},
                ignore_unavailable=True
            )
        except Exception as e:
            print(f"Cleanup ES Error: {e}")
    
    async def run_onboarding():
        tasks_status[db_id] = "running"
        try:
            # We would invoke the graph here
            initial_state = {
                "database_id": db_id,
                "database_name": request.database_name,
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

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

@router.delete("/onboard/{database_id}")
async def delete_database(database_id: str):
    """Removes a database and its trace from the Knowledge Graph"""
    if neo4j_driver:
        try:
            async with neo4j_driver.session() as session:
                cypher = """
                MATCH (db:Database {id: $db_id})
                OPTIONAL MATCH (db)-[:HAS_TABLE]->(t:Table)
                OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column)
                OPTIONAL MATCH (db)-[:CONTAINS]->(e:Entity)
                DETACH DELETE db, t, c, e
                """
                await session.run(cypher, db_id=database_id)
        except Exception:
            pass
            
    if es_client:
        try:
            await es_client.delete_by_query(
                index=f"{settings.ELASTICSEARCH_INDEX_PREFIX}entities",
                query={"match": {"database_id": database_id}},
                ignore_unavailable=True
            )
        except Exception:
            pass
            
    try:
        engine = create_async_engine(ORACLE_URL, connect_args={"timeout": 5})
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM onboarded_databases WHERE db_id = :db_id"), {"db_id": database_id})
        await engine.dispose()
    except Exception:
        pass
        
    tasks_status.pop(database_id, None)
    mock_db_connections.pop(database_id, None)
    
    registry = read_registry()
    if database_id in registry:
        del registry[database_id]
        write_registry(registry)
        
    return {"status": "deleted", "database_id": database_id}

@router.delete("/graph/clear")
async def clear_knowledge_graph():
    """Nuclear option to drop all entities and databases from Neo4j and ES"""
    if neo4j_driver:
        try:
            async with neo4j_driver.session() as session:
                await session.run("MATCH (n) DETACH DELETE n")
        except Exception:
            pass
            
    if es_client:
        try:
            await es_client.delete_by_query(
                index=f"{settings.ELASTICSEARCH_INDEX_PREFIX}entities",
                query={"match_all": {}},
                ignore_unavailable=True
            )
        except Exception:
            pass
            
    try:
        engine = create_async_engine(ORACLE_URL, connect_args={"timeout": 5})
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM onboarded_databases"))
        await engine.dispose()
    except Exception:
        pass
        
    tasks_status.clear()
    mock_db_connections.clear()
    write_registry({})
    return {"status": "graph cleared"}

@router.get("/onboard/{database_id}/status")
async def get_onboarding_status(database_id: str):
    return {"database_id": database_id, "status": tasks_status.get(database_id, "unknown")}


@router.post("/query")
async def ask_question(request: QueryRequest):
    """
    Executes the User Query workflow: NL -> SQL -> Validate -> Synthesize Answer.
    """
    # Grab the connection string from memory if database_id is provided
    conn_str = None
    if request.database_id and request.database_id != "selected-db-id":
        conn_str = mock_db_connections.get(request.database_id)
        if not conn_str:
            registry = read_registry()
            conn_str = registry.get(request.database_id, {}).get("connection_string")

    # Hazelcast Chat Session Caching
    chat_history = []
    session_id = f"chat_{request.database_id}" if request.database_id else f"chat_global"
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
        "relevant_context": {"connection_string": conn_str, "chat_history": chat_history} if conn_str else {"chat_history": chat_history},
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
            "database_id": final_state.get("database_id"),
            "database_name": final_state.get("database_name"),
            "answer": final_state.get("synthesized_answer", "Error synthesizing answer"),
            "sql_used": final_state.get("generated_sql"),
            "visualizations": final_state.get("recommended_visualizations"),
            "results": final_state.get("query_results")
        }
    except Exception as e:
        import traceback
        print("----- EXCEPTION IN QUERY ENDPOINT -----")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

from app.core.database import neo4j_driver

@router.get("/graph")
async def get_knowledge_graph():
    """Returns the Neo4j nodes and edges for the frontend visualization."""
    if not neo4j_driver:
        return {"nodes": [], "edges": []}
        
    async with neo4j_driver.session() as session:
        # Fetch all Entities and Databases
        nodes_res = await session.run("MATCH (n) WHERE n:Entity OR n:Database RETURN n.id AS id, coalesce(n.label, n.name, n.id) AS label, labels(n)[0] AS type")
        raw_nodes = await nodes_res.data()
        
        # Fetch all relationships
        edges_res = await session.run("MATCH (src)-[r]->(tgt) RETURN src.id AS source, tgt.id AS target, type(r) AS type")
        edges = await edges_res.data()
        
    return {
        "nodes": [
            {
                "id": n["id"], 
                "type": "input" if n["type"] == "Database" else "default", 
                "data": {"label": f"{n['type']}:\n{n['label']}" if n["type"] == "Database" else n["label"]}, 
                "position": {"x": 0, "y": 0}
            }
            for n in raw_nodes if n.get("id")
        ],
        "edges": [
            {"id": f"{e['source']}-{e['target']}-{e['type']}", "source": e["source"], "target": e["target"], "label": e["type"], "animated": e["type"] != "CONTAINS"}
            for e in edges if e.get("source") and e.get("target")
        ]
    }

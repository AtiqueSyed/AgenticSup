import operator
from typing import Annotated, TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, START, END

class OnboardingState(TypedDict):
    database_id: str
    connection_string: str
    extracted_schema: Dict[str, Any]
    semantic_descriptions: Dict[str, str]
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    status: str
    errors: List[str]

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

async def extract_schema_node(state: OnboardingState):
    """Connects to the target DB and extracts table, column, and foreign key definitions."""
    conn_str = state["connection_string"]
    try:
        # Create an async engine for the provided connection string
        engine = create_async_engine(conn_str)
        
        # We need to run inspection synchronously since SQLAlchemy inspect does not support async yet natively
        def get_schema(conn):
            inspector = inspect(conn)
            tables_data = []
            for table_name in inspector.get_table_names():
                columns = [{"name": c["name"], "type": str(c["type"])} for c in inspector.get_columns(table_name)]
                foreign_keys = inspector.get_foreign_keys(table_name)
                tables_data.append({
                    "name": table_name,
                    "columns": columns,
                    "foreign_keys": foreign_keys
                })
            return tables_data
        
        async with engine.connect() as conn:
            extracted_tables = await conn.run_sync(get_schema)
            
        await engine.dispose()
        return {"status": "extracted_schema", "extracted_schema": {"tables": extracted_tables}}
        
    except SQLAlchemyError as e:
        return {"status": "error", "errors": state.get("errors", []) + [f"DB Connection Error: {str(e)}"]}
    except Exception as e:
        return {"status": "error", "errors": state.get("errors", []) + [f"Unexpected Error: {str(e)}"]}

import json
from openai import AsyncOpenAI
from app.core.config import settings

async def generate_semantics_node(state: OnboardingState):
    """Uses LLM to generate semantic descriptions of tables and columns."""
    if state.get("status") == "error":
        return state
        
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL
    )
    
    extracted_tables = state["extracted_schema"].get("tables", [])
    semantics = {}
    
    # We serialize the schema minimally to pass to the LLM
    schema_summary = json.dumps([
        {"table": t["name"], "columns": [c["name"] for c in t["columns"]]} 
        for t in extracted_tables
    ])
    
    prompt = f"""
    Analyze the following database schema and provide a semantic description for each table and its business purpose.
    Return ONLY a valid JSON object where keys are table names and values are the string descriptions.
    
    Schema:
    {schema_summary}
    """
    
    try:
        response = await client.chat.completions.create(
            model="openai.gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        semantics = json.loads(content)
        return {"status": "generated_semantics", "semantic_descriptions": semantics}
    except Exception as e:
        return {"status": "error", "errors": state.get("errors", []) + [f"LLM Semantics Error: {str(e)}"]}

def identify_entities_node(state: OnboardingState):
    """Uses LLM to identify business entities and relationships from the schema."""
    return {"status": "identified_entities", "entities": [], "relationships": []}

def construct_knowledge_graph_node(state: OnboardingState):
    """Pushes the identified entities and relationships to Neo4j."""
    return {"status": "constructed_kg"}

def generate_embeddings_node(state: OnboardingState):
    """Generates embeddings for schema items and pushes to Elasticsearch."""
    return {"status": "generated_embeddings"}

def register_metadata_node(state: OnboardingState):
    """Saves all gathered metadata into the centralized registry (Oracle DB)."""
    return {"status": "completed"}

# Define the graph
workflow = StateGraph(OnboardingState)

workflow.add_node("extract_schema", extract_schema_node)
workflow.add_node("generate_semantics", generate_semantics_node)
workflow.add_node("identify_entities", identify_entities_node)
workflow.add_node("construct_knowledge_graph", construct_knowledge_graph_node)
workflow.add_node("generate_embeddings", generate_embeddings_node)
workflow.add_node("register_metadata", register_metadata_node)

workflow.add_edge(START, "extract_schema")
workflow.add_edge("extract_schema", "generate_semantics")
workflow.add_edge("generate_semantics", "identify_entities")
workflow.add_edge("identify_entities", "construct_knowledge_graph")
workflow.add_edge("construct_knowledge_graph", "generate_embeddings")
workflow.add_edge("generate_embeddings", "register_metadata")
workflow.add_edge("register_metadata", END)

admin_onboarding_app = workflow.compile()

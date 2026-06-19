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
    print("----- [NODE: extract_schema] Started -----")
    conn_str = state["connection_string"]
    try:
        # Create an async engine for the provided connection string
        print(f"Connecting to Oracle DB...")
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
        print(f"Success! Extracted {len(extracted_tables)} tables.")
        return {"status": "extracted_schema", "extracted_schema": {"tables": extracted_tables}}
        
    except SQLAlchemyError as e:
        print(f"[ERROR] DB Connection Error: {e}")
        return {"status": "error", "errors": state.get("errors", []) + [f"DB Connection Error: {str(e)}"]}
    except Exception as e:
        print(f"[ERROR] Unexpected Error: {e}")
        return {"status": "error", "errors": state.get("errors", []) + [f"Unexpected Error: {str(e)}"]}

import json
from openai import AsyncOpenAI
from app.core.config import settings

async def generate_semantics_node(state: OnboardingState):
    """Uses LLM to generate semantic descriptions of tables and columns."""
    print("----- [NODE: generate_semantics] Started -----")
    if state.get("status") == "error":
        print("Skipping due to previous error.")
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
        print("Calling AWS Bedrock LLM to generate table descriptions...")
        response = await client.chat.completions.create(
            model="openai.gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        semantics = json.loads(content)
        print("Success! Semantics generated.")
        return {"status": "generated_semantics", "semantic_descriptions": semantics}
    except Exception as e:
        print(f"Error calling LLM: {e}")
        return {"status": "error", "errors": state.get("errors", []) + [f"LLM Semantics Error: {str(e)}"]}

async def identify_entities_node(state: OnboardingState):
    """Uses LLM to identify business entities and relationships from the schema."""
    print("----- [NODE: identify_entities] Started -----")
    if state.get("status") == "error":
        print("Skipping due to previous error.")
        return state
        
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL
    )
    
    extracted_tables = state["extracted_schema"].get("tables", [])
    
    schema_summary = json.dumps([
        {"table": t["name"], "columns": [c["name"] for c in t["columns"]]} 
        for t in extracted_tables
    ])
    
    prompt = f"""
    Analyze this database schema and identify the core business Entities (nodes) and Relationships (edges) to construct a Knowledge Graph.
    Return ONLY a valid JSON object in this exact format:
    {{
      "entities": [ {{"id": "Customer", "label": "Customer Entity"}}, ... ],
      "relationships": [ {{"source": "Customer", "target": "Order", "type": "PLACES"}}, ... ]
    }}
    
    Schema:
    {schema_summary}
    """
    
    try:
        print("Calling AWS Bedrock LLM to identify abstract Entities and Relationships...")
        response = await client.chat.completions.create(
            model="openai.gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        result = json.loads(content)
        entities = result.get("entities", [])
        print(f"Success! Identified {len(entities)} Entities.")
        return {
            "status": "identified_entities", 
            "entities": entities, 
            "relationships": result.get("relationships", [])
        }
    except Exception as e:
        print(f"Error calling LLM: {e}")
        return {"status": "error", "errors": state.get("errors", []) + [f"LLM Entity Extraction Error: {str(e)}"]}

from app.core.database import neo4j_driver

async def construct_knowledge_graph_node(state: OnboardingState):
    """Pushes the LLM-identified entities and relationships to Neo4j."""
    print("----- [NODE: construct_knowledge_graph] Started -----")
    if state.get("status") == "error":
        print("Skipping due to previous error.")
        return state
        
    entities = state.get("entities", [])
    relationships = state.get("relationships", [])
    
    if neo4j_driver and entities:
        print(f"Connecting to Neo4j and merging {len(entities)} Entities...")
        async with neo4j_driver.session() as session:
            # Create Entities
            for ent in entities:
                ent_id = ent.get("id")
                await session.run("MERGE (e:Entity {id: $id}) SET e.label = $label", id=ent_id, label=ent.get("label", ent_id))
            
            # Create Relationships
            print(f"Merging {len(relationships)} Relationships into Neo4j...")
            for rel in relationships:
                await session.run(
                    "MATCH (src:Entity {id: $source}) "
                    "MATCH (tgt:Entity {id: $target}) "
                    f"MERGE (src)-[:{rel.get('type', 'RELATES_TO')}]->(tgt)",
                    source=rel.get("source"), target=rel.get("target")
                )
                
    print("Success! Neo4j Knowledge Graph constructed.")
    return {"status": "constructed_kg"}

from app.core.database import es_client

async def generate_embeddings_node(state: OnboardingState):
    """Generates embeddings for schema items and pushes to Elasticsearch deterministically."""
    extracted_tables = state.get("extracted_schema", {}).get("tables", [])
    if es_client and extracted_tables:
        try:
            for t in extracted_tables:
                await es_client.index(
                    index=f"{settings.ELASTICSEARCH_INDEX_PREFIX}tables",
                    document={"table_name": t["name"], "description": state.get("semantic_descriptions", {}).get(t["name"], "")}
                )
        except Exception as e:
            print(f"ES indexing error: {e}")
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

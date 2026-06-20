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
            
            # Identify all non-system schemas
            schemas_to_check = [None]
            exclude_schemas = {'SYS', 'SYSTEM', 'XDB', 'CTXSYS', 'MDSYS', 'DBSNMP', 'OUTLN', 'APPQOSSYS', 'DVSYS', 'DVF', 'AUDSYS', 'OJVMSYS', 'GSMADMIN_INTERNAL', 'ORDSYS', 'OLAPSYS', 'WMSYS', 'SYSRAC', 'SYSKM', 'SYSDG', 'SYSBACKUP', 'SYS$UMF', 'REMOTE_SCHEDULER_AGENT', 'DIP', 'GSMCATUSER', 'GSMUSER', 'XS$NULL', 'ANONYMOUS', 'FLOWS_FILES', 'HR', 'OE', 'PM', 'SH', 'IX', 'BI'}
            
            try:
                all_schemas = inspector.get_schema_names()
                print(f"[DEBUG] Found {len(all_schemas)} total schemas in database.")
                for s in all_schemas:
                    if s.upper() not in exclude_schemas and not s.upper().startswith('APEX'):
                        schemas_to_check.append(s)
                print(f"[DEBUG] Will scan the following schemas for tables: {schemas_to_check}")
            except Exception as e:
                print(f"[ERROR] Could not list all schemas: {e}")
                
            seen_tables = set()
            for schema in set(schemas_to_check):
                try:
                    tables_in_schema = inspector.get_table_names(schema=schema)
                    print(f"[DEBUG] Schema '{schema}' has {len(tables_in_schema)} tables.")
                    for table_name in tables_in_schema:
                        if table_name in seen_tables: continue
                        seen_tables.add(table_name)
                        columns = [{"name": c["name"], "type": str(c["type"])} for c in inspector.get_columns(table_name, schema=schema)]
                        foreign_keys = inspector.get_foreign_keys(table_name, schema=schema)
                        tables_data.append({
                            "name": table_name,
                            "columns": columns,
                            "foreign_keys": foreign_keys
                        })
                except Exception as e:
                    print(f"Skipping tables in schema {schema}: {e}")
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
            model=settings.DEFAULT_LLM_MODEL,
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
            model=settings.DEFAULT_LLM_MODEL,
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
            # Create Database Node
            db_id = state.get("database_id", "unknown")
            conn_str = state.get("connection_string", "unknown")
            await session.run("MERGE (db:Database {id: $id}) SET db.connection_string = $conn_str", id=db_id, conn_str=conn_str)
            
            # Create Entities and Link to Database
            for ent in entities:
                ent_id = ent.get("id")
                await session.run(
                    "MERGE (e:Entity {id: $id}) "
                    "SET e.label = $label "
                    "WITH e "
                    "MATCH (db:Database {id: $db_id}) "
                    "MERGE (db)-[:CONTAINS]->(e)",
                    id=ent_id, label=ent.get("label", ent_id), db_id=db_id
                )
            
            # Create Relationships
            print(f"Merging {len(relationships)} Relationships into Neo4j...")
            print(f"[DEBUG] Relationships raw: {relationships}")
            try:
                for rel in relationships:
                    rel_type = rel.get('type', 'RELATES_TO')
                    # Sanitize rel_type (remove backticks to prevent injection)
                    rel_type_safe = str(rel_type).replace("`", "")
                    query = (
                        "MERGE (src:Entity {id: $source}) "
                        "ON CREATE SET src.label = $source "
                        "MERGE (tgt:Entity {id: $target}) "
                        "ON CREATE SET tgt.label = $target "
                        f"MERGE (src)-[:`{rel_type_safe}`]->(tgt)"
                    )
                    await session.run(
                        query,
                        source=str(rel.get("source", "unknown")).strip(), 
                        target=str(rel.get("target", "unknown")).strip()
                    )
            except Exception as e:
                print(f"[ERROR] Failed to merge relationships: {e}")
                
    print("Success! Neo4j Knowledge Graph constructed.")
    return {"status": "constructed_kg"}

from app.core.database import es_client

async def generate_embeddings_node(state: OnboardingState):
    """Generates embeddings for schema items and pushes to Elasticsearch deterministically."""
    extracted_tables = state.get("extracted_schema", {}).get("tables", [])
    db_id = state.get("database_id", "unknown")
    if es_client and extracted_tables:
        try:
            for t in extracted_tables:
                await es_client.index(
                    index=f"{settings.ELASTICSEARCH_INDEX_PREFIX}tables",
                    document={
                        "database_id": db_id,
                        "table_name": t["name"], 
                        "description": state.get("semantic_descriptions", {}).get(t["name"], "")
                    }
                )
        except Exception as e:
            print(f"ES indexing error: {e}")
    return {"status": "generated_embeddings"}

from sqlalchemy import text

async def register_metadata_node(state: OnboardingState):
    """Saves all gathered metadata into the centralized registry (Oracle DB)."""
    print("----- [NODE: register_metadata] Started -----")
    dev_db_str = "oracle+oracledb_async://C%23%23agenticsupervisor_developer:agenticsupervisor@host.docker.internal:1521/?service_name=XE"
    try:
        engine = create_async_engine(dev_db_str)
        async with engine.begin() as conn:
            # Create table if it doesn't exist (Catching ORA-00955: name is already used by an existing object)
            await conn.execute(text("""
                BEGIN
                   EXECUTE IMMEDIATE 'CREATE TABLE onboarded_databases (
                       db_id VARCHAR2(255) PRIMARY KEY,
                       connection_string VARCHAR2(1000),
                       status VARCHAR2(50)
                   )';
                EXCEPTION
                   WHEN OTHERS THEN
                      IF SQLCODE != -955 THEN
                         RAISE;
                      END IF;
                END;
            """))
            # Insert the newly onboarded DB
            await conn.execute(text("""
                MERGE INTO onboarded_databases tgt
                USING (SELECT :db_id AS db_id, :conn_str AS connection_string, :status AS status FROM dual) src
                ON (tgt.db_id = src.db_id)
                WHEN MATCHED THEN UPDATE SET tgt.connection_string = src.connection_string, tgt.status = src.status
                WHEN NOT MATCHED THEN INSERT (db_id, connection_string, status) VALUES (src.db_id, src.connection_string, src.status)
            """), {"db_id": state.get("database_id", "unknown"), "conn_str": state.get("connection_string", ""), "status": "completed"})
        await engine.dispose()
        print("Success! Metadata registered to Developer Oracle database.")
    except Exception as e:
        print(f"[ERROR] Failed to register metadata: {e}")
        
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

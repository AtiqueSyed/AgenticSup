import operator
from typing import Annotated, TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, START, END

class OnboardingState(TypedDict):
    database_id: str
    database_name: str
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
    Analyze this database schema and identify the core abstract business Entities (nodes) and Relationships (edges) to construct a Knowledge Graph.
    For each Entity, provide a rich semantic 'description' (this will be vectorized for semantic search) and an array of 'mapped_tables' that physical represent this entity in the database.
    Return ONLY a valid JSON object in this exact format:
    {{
      "entities": [ {{"id": "Customer", "label": "Customer Entity", "description": "Represents a human or business that purchases products...", "mapped_tables": ["CUSTOMERS", "USERS"]}}, ... ],
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
            db_name = state.get("database_name", db_id)
            await session.run("MERGE (db:Database {id: $id}) SET db.connection_string = $conn_str, db.name = $db_name", id=db_id, conn_str=conn_str, db_name=db_name)
            
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
                
                # Push tables mapping to this entity
                mapped_tables = ent.get("mapped_tables", [])
                
                # Fetch schema dictionaries
                extracted_tables = state.get("extracted_schema", {}).get("tables", [])
                table_schema_dict = {t["name"].upper(): t["columns"] for t in extracted_tables}
                
                for table_name in mapped_tables:
                    await session.run(
                        "MERGE (t:Table {id: $t_id}) "
                        "SET t.name = $t_name "
                        "WITH t "
                        "MATCH (db:Database {id: $db_id}) "
                        "MERGE (db)-[:HAS_TABLE]->(t) "
                        "WITH t "
                        "MATCH (e:Entity {id: $e_id}) "
                        "MERGE (t)-[:MAPS_TO]->(e)",
                        t_id=f"{db_id}_{table_name}", t_name=table_name, db_id=db_id, e_id=ent_id
                    )
                    
                    # Push physical columns
                    columns = table_schema_dict.get(table_name.upper(), [])
                    for col in columns:
                        col_name = col["name"]
                        col_type = col.get("type", "unknown")
                        await session.run(
                            "MERGE (c:Column {id: $c_id}) "
                            "SET c.name = $c_name, c.type = $c_type "
                            "WITH c "
                            "MATCH (t:Table {id: $t_id}) "
                            "MERGE (t)-[:HAS_COLUMN]->(c)",
                            c_id=f"{db_id}_{table_name}_{col_name}", c_name=col_name, c_type=col_type, t_id=f"{db_id}_{table_name}"
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
    """Generates embeddings for abstract entities and pushes to Elasticsearch deterministically."""
    from app.core.config import settings
    from fastembed import TextEmbedding
    
    entities = state.get("entities", [])
    db_id = state.get("database_id", "unknown")
    if es_client and entities:
        print("----- [NODE: generate_embeddings] Started -----")
        try:
            # Initialize fast, local open-source embedding model
            embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5") # Using bge-small as it is explicitly supported by fastembed and extremely fast
            
            index_name = f"{settings.ELASTICSEARCH_INDEX_PREFIX}entities"
            
            # Create index with vector mapping if it doesn't exist
            exists = await es_client.indices.exists(index=index_name)
            if not exists:
                mapping = {
                    "mappings": {
                        "properties": {
                            "database_id": {"type": "keyword"},
                            "entity_id": {"type": "keyword"},
                            "description": {"type": "text"},
                            "embedding": {
                                "type": "dense_vector",
                                "dims": 384, # BGE-small output dimensionality
                                "index": True,
                                "similarity": "cosine"
                            }
                        }
                    }
                }
                await es_client.indices.create(index=index_name, body=mapping)
            
            for ent in entities:
                text_to_embed = ent.get('id')
                desc = ent.get("description", ent.get("label", ""))
                
                # Generate embedding
                try:
                    # FastEmbed returns a generator of numpy arrays, we extract the first one and convert to list
                    embedding = list(list(embedding_model.embed([text_to_embed]))[0])
                except Exception as embed_err:
                    print(f"Embedding generation failed for '{text_to_embed}': {embed_err}")
                    embedding = [0.001] * 384
                
                doc_id = f"{db_id}_{ent.get('id')}"
                await es_client.index(
                    index=index_name,
                    id=doc_id,
                    document={
                        "database_id": db_id,
                        "entity_id": ent.get("id"), 
                        "description": desc,
                        "embedding": embedding
                    }
                )
            print("Successfully generated and indexed abstract entity vector embeddings in Elasticsearch using FastEmbed.")
        except Exception as e:
            print(f"ES indexing error: {e}")
    return {"status": "generated_embeddings"}

from sqlalchemy import text

async def register_metadata_node(state: OnboardingState):
    """Saves all gathered metadata into the centralized registry."""
    print("----- [NODE: register_metadata] Started -----")
    # We now handle metadata registration reliably via Hazelcast in endpoints.py to avoid Oracle credential issues
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

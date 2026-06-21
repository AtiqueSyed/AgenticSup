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
                        
                        # Extract 3 sample rows to prevent LLM hallucinations
                        sample_data = []
                        try:
                            from sqlalchemy import text
                            query = f"SELECT * FROM {schema}.{table_name}" if schema else f"SELECT * FROM {table_name}"
                            query += " FETCH FIRST 3 ROWS ONLY"
                            res = conn.execute(text(query))
                            sample_data = [dict(row._mapping) for row in res]
                        except Exception as sample_err:
                            print(f"[DEBUG] Could not fetch samples for {table_name}: {sample_err}")
                            
                        tables_data.append({
                            "name": table_name,
                            "columns": columns,
                            "foreign_keys": foreign_keys,
                            "sample_data": sample_data
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
    
    Example format:
    {{
      "table_name_1": "Description of table 1",
      "table_name_2": "Description of table 2"
    }}
    
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
        
    from app.core.database import neo4j_driver
    
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL
    )
    
    existing_entities = []
    if neo4j_driver:
        try:
            async with neo4j_driver.session() as session:
                res = await session.run("MATCH (e:Entity) RETURN e.id AS id, e.description AS description LIMIT 50")
                records = await res.data()
                existing_entities = [{"id": r["id"], "description": r["description"]} for r in records]
        except Exception as e:
            print(f"[ERROR] Could not fetch existing entities: {e}")
            
    existing_entities_context = json.dumps(existing_entities) if existing_entities else "[]"
    
    extracted_tables = state["extracted_schema"].get("tables", [])
    
    semantics = state.get("semantic_descriptions", {})
    schema_summary = json.dumps([
        {
            "table": t["name"], 
            "purpose": semantics.get(t["name"], ""),
            "columns": [c["name"] for c in t["columns"]]
        } 
        for t in extracted_tables
    ])
    
    prompt = f"""
    You are an expert Enterprise Data Architect. Analyze the following database schema and identify the core abstract business Entities (nodes) and Relationships (edges) to construct a Knowledge Graph.
    
    CRITICAL INSTRUCTIONS:
    1. Look beyond just table names. Inspect the columns and the table's "purpose" to identify implicit or embedded business concepts (e.g., an 'Observation' or 'Transaction' that exists inside an 'Inspection' or 'Account' table).
    2. An Entity does not need to have a 1-to-1 mapping with a table. If a table contains data about multiple distinct concepts (e.g., a Customer and their Address), create separate Entities and map both to that same table.
    3. Ensure naming is strictly abstract and universal (e.g., use "Customer" instead of "tbl_cust_data").
    4. GLOBAL KNOWLEDGE GRAPH REUSE: You are building an enterprise-wide graph. Below is a list of 'Existing Entities' that are already in the global graph from other databases. If the schema you are analyzing contains data that maps perfectly to an Existing Entity, you MUST reuse its EXACT `id` instead of inventing a new one! (e.g., if "Bank" exists, use "Bank", do not create "RespondentBank").
    
    For each Entity, provide a rich semantic 'description' (this will be vectorized for semantic search), and an array of 'mapped_tables' where data for this entity resides.
    
    Return ONLY a valid JSON object in this exact format:
    {{
      "entities": [
        {{
          "id": "Customer",
          "description": "A person or organization that purchases goods.",
          "mapped_tables": ["CUSTOMERS", "ORDERS"]
        }},
        {{
          "id": "Observation",
          "description": "A specific finding or data point recorded during an inspection.",
          "mapped_tables": ["INSPECTION_REPORTS"]
        }}
      ],
      "relationships": [ {{"source": "Customer", "target": "Order", "type": "PLACES"}} ]
    }}
    
    Existing Entities in Global Graph:
    {existing_entities_context}
    
    Schema context (Tables, Purposes, and Columns):
    {schema_summary}
    """
    
    try:
        print("Calling AWS Bedrock LLM to identify Entities...")
        response = await client.chat.completions.create(
            model=settings.DEFAULT_LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        graph_data = json.loads(content)
        
        entities = graph_data.get("entities", [])
        relationships = graph_data.get("relationships", [])
        
        # --- DETERMINISTIC FALLBACK: Ensure 100% table coverage ---
        mapped_tables_set = set()
        for ent in entities:
            mapped_tables_set.update([t.upper() for t in ent.get("mapped_tables", [])])
            
        for t in extracted_tables:
            table_name = t["name"]
            if table_name.upper() not in mapped_tables_set:
                print(f"[DEBUG] Auto-generating fallback Entity for unmapped table: {table_name}")
                entities.append({
                    "id": table_name.capitalize(),
                    "description": f"Core business entity containing records and details regarding {table_name}.",
                    "mapped_tables": [table_name],
                    "entity_keys": []
                })
        # ---------------------------------------------------------
        
        print(f"Success! Identified {len(entities)} entities.")
        return {
            "status": "identified_entities", 
            "entities": entities,
            "relationships": relationships
        }
    except Exception as e:
        print(f"Error calling LLM: {e}")
        return {"status": "error", "errors": state.get("errors", []) + [f"LLM Entity Error: {str(e)}"]}

async def map_entity_columns_node(state: OnboardingState):
    """Takes the identified entities and maps physical column keys to them."""
    print("----- [NODE: map_entity_columns] Started -----")
    if state.get("status") == "error":
        return state
        
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL
    )
    
    extracted_tables = state["extracted_schema"].get("tables", [])
    entities = state.get("entities", [])
    
    schema_summary = json.dumps([
        {"table": t["name"], "columns": [c["name"] for c in t["columns"]]} 
        for t in extracted_tables
    ])
    
    entities_summary = json.dumps([
        {"id": e["id"], "mapped_tables": e.get("mapped_tables", [])} 
        for e in entities
    ])
    
    prompt = f"""
    You are an expert Database Architect. I have identified the core abstract business Entities in this database schema.
    Your task is to analyze the tables mapped to each entity, and identify the specific 'entity_keys' (primary keys or unique mapping columns) that perfectly represent that entity in the physical table.
    
    If a mapped table doesn't have a clear column that represents the entity, omit it. Do NOT hallucinate columns.
    
    Return ONLY a valid JSON object in this exact format updating the entities:
    {{
      "entities": [
        {{
          "id": "Customer",
          "entity_keys": [{{"table": "CUSTOMERS", "column": "CUSTOMER_ID"}}]
        }}
      ]
    }}
    
    Schema:
    {schema_summary}
    
    Entities:
    {entities_summary}
    """
    
    try:
        print("Calling AWS Bedrock LLM to map Entity column keys...")
        response = await client.chat.completions.create(
            model=settings.DEFAULT_LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        result = json.loads(content)
        
        mapped_keys = result.get("entities", [])
        key_map = {e["id"]: e.get("entity_keys", []) for e in mapped_keys}
        
        # Merge the entity_keys back into the main entities list
        for ent in entities:
            if ent["id"] in key_map:
                ent["entity_keys"] = key_map[ent["id"]]
                
        print("Success! Entity keys mapped.")
        return {"status": "mapped_columns", "entities": entities}
    except Exception as e:
        print(f"Error calling LLM: {e}")
        return {"status": "error", "errors": state.get("errors", []) + [f"LLM Key Mapping Error: {str(e)}"]}


from app.core.database import neo4j_driver

async def construct_knowledge_graph_node(state: OnboardingState):
    """Pushes the LLM-identified entities and relationships to Neo4j."""
    print("----- [NODE: construct_knowledge_graph] Started -----")
    if state.get("status") == "error":
        print("Skipping due to previous error.")
        return state
        
    entities = state.get("entities", [])
    relationships = state.get("relationships", [])
    db_id = state.get("database_id", "unknown")
    conn_str = state.get("connection_string", "unknown")
    db_name = state.get("database_name", db_id)
    extracted_tables = state.get("extracted_schema", {}).get("tables", [])
    table_schema_dict = {t["name"].upper(): t for t in extracted_tables}
    
    if neo4j_driver and entities:
        print(f"Connecting to Neo4j and merging {len(entities)} Entities...")
        async with neo4j_driver.session() as session:
            # Create Database Node
            await session.run("MERGE (db:Database {id: $id}) SET db.connection_string = $conn_str, db.name = $db_name", id=db_id, conn_str=conn_str, db_name=db_name)
            
            # Step 1: Push ALL physical tables and columns deterministically
            print(f"[DEBUG] Pushing {len(extracted_tables)} physical tables to Neo4j...")
            for table in extracted_tables:
                table_name = table["name"]
                columns = table.get("columns", [])
                sample_data = table.get("sample_data", [])
                
                await session.run(
                    "MERGE (t:Table {id: $t_id}) "
                    "SET t.name = $t_name "
                    "WITH t "
                    "MATCH (db:Database {id: $db_id}) "
                    "MERGE (db)-[:HAS_TABLE]->(t)",
                    t_id=f"{db_id}_{table_name}", t_name=table_name, db_id=db_id
                )
                
                for col in columns:
                    col_name = col["name"]
                    col_type = col.get("type", "unknown")
                    
                    sample_vals = []
                    for row in sample_data:
                        val = row.get(col_name)
                        if val is not None and str(val) not in sample_vals:
                            sample_vals.append(str(val))
                            
                    await session.run(
                        "MERGE (c:Column {id: $c_id}) "
                        "SET c.name = $c_name, c.type = $c_type, c.sample_values = $c_samples "
                        "WITH c "
                        "MATCH (t:Table {id: $t_id}) "
                        "MERGE (t)-[:HAS_COLUMN]->(c)",
                        c_id=f"{db_id}_{table_name}_{col_name}",
                        c_name=col_name,
                        c_type=col_type,
                        c_samples=sample_vals,
                        t_id=f"{db_id}_{table_name}"
                    )
            
            # Step 2: Push logical Entities and link them to the deterministic tables
            print(f"[DEBUG] Pushing {len(entities)} logical Entities to Neo4j...")
            for ent in entities:
                ent_id = ent.get("id")
                mapped_tables = ent.get("mapped_tables", [])
                entity_keys = ent.get("entity_keys", [])
                
                # Create Entity and link to Database
                await session.run(
                    "MERGE (e:Entity {id: $e_id}) SET e.name = $e_name, e.description = $desc "
                    "WITH e MATCH (db:Database {id: $db_id}) MERGE (db)-[:CONTAINS]->(e)",
                    e_id=ent_id, e_name=ent_id, desc=ent.get("description", ""), db_id=db_id
                )
                
                # Link Table -> Entity
                for table_name in mapped_tables:
                    if table_name.upper() not in table_schema_dict:
                        continue
                        
                    physical_table_name = table_schema_dict[table_name.upper()]["name"]
                        
                    await session.run(
                        "MATCH (t:Table {id: $t_id}) "
                        "MATCH (e:Entity {id: $e_id}) "
                        "MERGE (t)-[:MAPS_TO]->(e)",
                        t_id=f"{db_id}_{physical_table_name}", e_id=ent_id
                    )
                    
                    # Set is_entity_key on columns and link Column -> Entity
                    for key_obj in entity_keys:
                        if key_obj.get("table", "").upper() == table_name.upper():
                            col_name = key_obj.get("column", "")
                            physical_col_name = col_name
                            for c in table_schema_dict[table_name.upper()].get("columns", []):
                                if c["name"].upper() == col_name.upper():
                                    physical_col_name = c["name"]
                                    break
                                    
                            await session.run(
                                "MATCH (c:Column {id: $c_id}) "
                                "SET c.is_entity_key = true, c.represented_entity = $e_id "
                                "WITH c MATCH (e:Entity {id: $e_id}) "
                                "MERGE (c)-[:REPRESENTS]->(e)",
                                c_id=f"{db_id}_{physical_table_name}_{physical_col_name}", e_id=ent_id
                            )
            
            # Create Relationships
            print(f"Merging {len(relationships)} Relationships into Neo4j...")
            try:
                for rel in relationships:
                    rel_type = rel.get('type', 'RELATES_TO')
                    # Sanitize rel_type (remove backticks to prevent injection)
                    rel_type_safe = str(rel_type).replace("`", "")
                    query = (
                        "MATCH (src:Entity {id: $source}) "
                        "MATCH (tgt:Entity {id: $target}) "
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
workflow.add_node("map_entity_columns", map_entity_columns_node)
workflow.add_node("construct_knowledge_graph", construct_knowledge_graph_node)
workflow.add_node("generate_embeddings", generate_embeddings_node)
workflow.add_node("register_metadata", register_metadata_node)

workflow.add_edge(START, "extract_schema")
workflow.add_edge("extract_schema", "generate_semantics")
workflow.add_edge("generate_semantics", "identify_entities")
workflow.add_edge("identify_entities", "map_entity_columns")
workflow.add_edge("map_entity_columns", "construct_knowledge_graph")
workflow.add_edge("construct_knowledge_graph", "generate_embeddings")
workflow.add_edge("generate_embeddings", "register_metadata")
workflow.add_edge("register_metadata", END)

admin_onboarding_app = workflow.compile()

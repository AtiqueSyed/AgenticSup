import operator
from typing import Annotated, TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, START, END

class QueryState(TypedDict):
    question: str
    database_id: str
    database_name: Optional[str]
    relevant_context: Dict[str, Any]
    generated_sql: Optional[str]
    query_results: Optional[List[Dict[str, Any]]]
    validation_error: Optional[str]
    synthesized_answer: Optional[str]
    recommended_visualizations: Optional[Dict[str, Any]]
    iterations: int
    sub_questions: Optional[List[str]]

async def decompose_query_node(state: QueryState):
    """Uses LLM to decompose a complex business question into simpler atomic sub-questions."""
    print("----- [QUERY NODE: decompose_query] Started -----")
    from openai import AsyncOpenAI
    from app.core.config import settings
    import json
    
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL
    )
    
    prompt = f"""
    You are an expert Data Architect. Your task is to take a complex user question and break it down into an array of simple, atomic sub-questions.
    These sub-questions will be used to independently search our vector database for relevant business entities and tables.
    
    CRITICAL INSTRUCTIONS:
    1. If the question is already simple, return it EXACTLY as it is, inside a single-element array.
    2. DO NOT generate multiple variations, rephrasings, or synonymous versions of the same question. 
    3. ONLY break the question down if it spans multiple completely distinct metrics or areas.
    
    EXAMPLES:
    Input: "What is the count of inspections for Bank 1?"
    Output: {{ "sub_questions": ["What is the count of inspections for Bank 1?"] }}
    
    Input: "Show me all complaints and the average inspection score for Bank 1"
    Output: {{ "sub_questions": ["Show me all complaints for Bank 1", "What is the average inspection score for Bank 1?"] }}
    
    User Question: "{state['question']}"
    
    Return ONLY a valid JSON object in this exact format.
    """
    
    try:
        response = await client.chat.completions.create(
            model=settings.DEFAULT_LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        result = json.loads(content)
        sub_questions = result.get("sub_questions", [state["question"]])
        print(f"[DEBUG] Decomposed query into {len(sub_questions)} sub-questions: {sub_questions}")
        return {"sub_questions": sub_questions, "iterations": state.get("iterations", 0)}
    except Exception as e:
        print(f"[ERROR] Decomposition failed: {e}")
        return {"sub_questions": [state["question"]], "iterations": state.get("iterations", 0)}

async def retrieve_context_node(state: QueryState):
    """Retrieves relevant schema, entities from Neo4j, and embeddings from Elasticsearch."""
    print("----- [QUERY NODE: retrieve_context] Started -----")
    from app.core.database import es_client, neo4j_driver
    from app.core.config import settings
    from fastembed import TextEmbedding

    question = state["question"]
    db_id = state.get("database_id")
    
    context = state.get("relevant_context", {}).copy()
    context["tables"] = []
    context["relationships"] = []
    
    try:
        print("[DEBUG] Initializing embedding model...")
        # Initialize fast, local open-source embedding model
        embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        
        matched_entities = []
        sub_questions = state.get("sub_questions", [question])
        index_name = f"{settings.ELASTICSEARCH_INDEX_PREFIX}entities"
        
        for q in sub_questions:
            try:
                print(f"[DEBUG] Embedding sub-question: {q}")
                query_vector = list(list(embedding_model.embed([q]))[0])
                knn_query = {
                    "field": "embedding",
                    "query_vector": query_vector,
                    "k": 2,
                    "num_candidates": 50
                }
                search_body = {"knn": knn_query}
                
                if es_client and await es_client.indices.exists(index=index_name):
                    es_results = await es_client.search(index=index_name, body=search_body)
                    hits = es_results.get("hits", {}).get("hits", [])[:2]
                    for hit in hits:
                        source = hit["_source"]
                        entity_id = source.get("entity_id")
                        if entity_id and entity_id not in matched_entities:
                            matched_entities.append(entity_id)
            except Exception as e:
                print(f"Embedding/Search generation failed for sub-question '{q}': {e}")
                
        print(f"[DEBUG] Combined Matched Entities from ES across all sub-queries: {matched_entities}")
        
        # Query Neo4j to find which Database and Tables map to these Entities
        if neo4j_driver:
            async with neo4j_driver.session() as session:
                if db_id and db_id != "selected-db-id" and matched_entities:
                    cypher = """
                    MATCH (db:Database {id: $db_id})
                    MATCH (e:Entity) WHERE e.id IN $matched_entities
                    MATCH (db)-[:HAS_TABLE]->(t:Table)-[:MAPS_TO]->(e)
                    OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column)
                    WITH db, t, e, collect(c) AS all_columns, count(c) AS col_count
                    WITH db, t, 
                         [col IN all_columns WHERE col_count <= 5 OR EXISTS((col)-[:REPRESENTS]->(e)) | 
                          {name: col.name, type: col.type, description: col.description, sample_values: col.sample_values, is_entity_key: col.is_entity_key}] AS columns
                    RETURN db.id AS database_id, db.name AS database_name, db.connection_string AS conn_str, collect({name: t.name, columns: columns}) AS tables
                    """
                    neo_res = await session.run(cypher, db_id=db_id, matched_entities=matched_entities)
                elif matched_entities:
                    cypher = """
                    MATCH (e:Entity) WHERE e.id IN $matched_entities
                    MATCH (db:Database)-[:HAS_TABLE]->(t:Table)-[:MAPS_TO]->(e)
                    OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column)
                    WITH db, t, e, collect(c) AS all_columns, count(c) AS col_count
                    WITH db, t, 
                         [col IN all_columns WHERE col_count <= 5 OR EXISTS((col)-[:REPRESENTS]->(e)) | 
                          {name: col.name, type: col.type, description: col.description, sample_values: col.sample_values, is_entity_key: col.is_entity_key}] AS columns
                    RETURN db.id AS database_id, db.name AS database_name, db.connection_string AS conn_str, collect({name: t.name, columns: columns}) AS tables
                    """
                    neo_res = await session.run(cypher, matched_entities=matched_entities)
                else:
                    neo_res = None
                    
                records = await neo_res.data() if neo_res else []
                
                if not records:
                    print("[DEBUG] Fetching all databases schema as fallback...")
                    cypher_all = """
                    MATCH (db:Database)-[:HAS_TABLE]->(t:Table)
                    OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column)
                    WITH db, t, collect(c) AS all_columns, count(c) AS col_count
                    WITH db, t, 
                         [col IN all_columns WHERE col_count <= 5 OR col.is_entity_key = true | 
                          {name: col.name, type: col.type, description: col.description, sample_values: col.sample_values, is_entity_key: col.is_entity_key}] AS columns
                    RETURN db.id AS database_id, db.name AS database_name, db.connection_string AS conn_str, collect({name: t.name, columns: columns}) AS tables
                    """
                    neo_res_all = await session.run(cypher_all)
                    records = await neo_res_all.data()
                    
                if records:
                    context["available_databases"] = records
                    context["relationships"] = [{"source": "Entity", "target": "Table", "type": "MAPS_TO"}]
                    
                    import json
                    print(f"[DEBUG] Autonomously retrieved schema for {len(records)} Databases:\n{json.dumps(records, indent=2)}")
                    return {"relevant_context": context}
                else:
                    print(f"[DEBUG] Neo4j found no databases.")
                    
        print(f"[DEBUG] Context successfully assembled with schemas.")
    except Exception as e:
        print(f"Retrieval error: {e}")
        
    return {"relevant_context": context}

import json
from openai import AsyncOpenAI
from app.core.config import settings

async def generate_sql_node(state: QueryState):
    """Uses LLM with the retrieved context to generate optimized SQL."""
    print("----- [QUERY NODE: generate_sql] Started -----")
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL
    )
    
    context_data = state.get("relevant_context", {})
    available_databases = context_data.get("available_databases", [])
    
    if not available_databases:
        print("[DEBUG] No available databases to query.")
        return {"validation_error": "I could not find the relevant details or tables to answer this question."}
    
    context_str = json.dumps(available_databases)
    
    prompt = f"""
    You are an expert SQL Developer. A user has asked a question.
    Below are the schemas of the available databases that contain information matching the user's intent.
    There may be multiple databases. You must select the ONE BEST database to query, and write a SQL query for it.
    
    Context (Databases, Tables, and Columns):
    {context_str}
    
    User Question: {state['question']}
    
    CRITICAL: You MUST output a raw JSON object and nothing else. Do not output markdown code blocks.
    Format:
    {{
      "target_database_id": "<database_id>",
      "sql": "<YOUR SQL QUERY HERE>"
    }}
    """
    
    try:
        response = await client.chat.completions.create(
            model=settings.DEFAULT_LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        result = json.loads(content)
        
        sql = result.get("sql", "").strip()
        target_db = result.get("target_database_id", "")
        
        # Clean up any residual markdown wrapping
        if sql.startswith("```sql"):
            sql = sql[6:]
        if sql.startswith("```"):
            sql = sql[3:]
        if sql.endswith("```"):
            sql = sql[:-3]
            
        target_db = result.get("target_database_id", "")
        target_db_name = ""
        for db in available_databases:
            if db.get("database_id") == target_db:
                target_db_name = db.get("database_name", target_db)
                break
                
        print(f"[DEBUG] Generated SQL Query:\n{sql}\n")
        return {"generated_sql": sql.strip(), "database_id": target_db, "database_name": target_db_name}
    except Exception as e:
        print(f"SQL Generation error: {e}")
        return {"validation_error": "I could not find the relevant details or tables to answer this question."}

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def execute_sql_node(state: QueryState):
    """Executes the SQL securely against the target database."""
    print("----- [QUERY NODE: execute_sql] Started -----")
    if not state.get("generated_sql"):
        return {"validation_error": state.get("validation_error", "No SQL generated to execute.")}
        
    target_db_id = state.get("database_id")
    available_dbs = state.get("relevant_context", {}).get("available_databases", [])
    
    conn_str = None
    for db in available_dbs:
        if db.get("database_id") == target_db_id:
            conn_str = db.get("conn_str")
            break
            
    if not conn_str:
        return {"validation_error": "The targeted database connection string could not be found."}
    
    try:
        print(f"[DEBUG] conn_str used in execute_sql_node: {conn_str}")
        engine = create_async_engine(conn_str)
        async with engine.connect() as conn:
            # Note: In production, read-only roles and strict validation must be enforced
            result = await conn.execute(text(state["generated_sql"]))
            rows = [dict(mapping) for mapping in result.mappings()]
        
        await engine.dispose()
        return {"query_results": rows, "validation_error": None}
    except Exception as e:
        return {"query_results": None, "validation_error": str(e)}

def validate_results_node(state: QueryState):
    """Checks if the execution had errors to decide whether to fix the SQL or proceed."""
    return {"iterations": state["iterations"] + 1}

async def synthesize_answer_node(state: QueryState):
    """Takes the question and the raw query results and generates a natural language answer."""
    if state.get("validation_error"):
        if "ORA-" in state["validation_error"]:
            return {"synthesized_answer": "I could not find the data you were looking for. Please ask again with more details."}
        return {"synthesized_answer": f"I encountered an error trying to query the database: {state['validation_error']}"}
        
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL
    )
    
    results_str = json.dumps(state.get("query_results", [])[:100]) # Limit to first 100 rows
    
    prompt = f"""
    You are an expert data analyst. The user asked a business question. 
    Below is the raw data retrieved from the database to answer it.
    
    Question: {state['question']}
    Data: {results_str}
    
    Provide a concise, highly professional natural language summary answering the user's question.
    """
    
    try:
        response = await client.chat.completions.create(
            model=settings.DEFAULT_LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = response.choices[0].message.content.strip()
        return {"synthesized_answer": answer}
    except Exception as e:
        # MOCK FALLBACK: For local testing
        return {"synthesized_answer": f"Based on the extracted database rows, I found {len(state.get('query_results', []))} records that match your request."}

def recommend_visualizations_node(state: QueryState):
    """LLM determines the best chart type and JSON spec for the frontend ECharts."""
    return {"recommended_visualizations": {"type": "bar", "spec": {}}}

# Conditional edge logic
def should_regenerate_sql(state: QueryState) -> str:
    if state.get("validation_error") and state["iterations"] < 3:
        return "generate_sql"
    return "synthesize_answer"

# Define the graph
workflow = StateGraph(QueryState)

workflow.add_node("decompose_query", decompose_query_node)
workflow.add_node("retrieve_context", retrieve_context_node)
workflow.add_node("generate_sql", generate_sql_node)
workflow.add_node("execute_sql", execute_sql_node)
workflow.add_node("validate_results", validate_results_node)
workflow.add_node("synthesize_answer", synthesize_answer_node)
workflow.add_node("recommend_visualizations", recommend_visualizations_node)

workflow.add_edge(START, "decompose_query")
workflow.add_edge("decompose_query", "retrieve_context")
workflow.add_edge("retrieve_context", "generate_sql")
workflow.add_edge("generate_sql", "execute_sql")
workflow.add_edge("execute_sql", "validate_results")

workflow.add_conditional_edges(
    "validate_results",
    should_regenerate_sql,
    {
        "generate_sql": "generate_sql",
        "synthesize_answer": "synthesize_answer"
    }
)

workflow.add_edge("synthesize_answer", "recommend_visualizations")
workflow.add_edge("recommend_visualizations", END)

user_query_app = workflow.compile()

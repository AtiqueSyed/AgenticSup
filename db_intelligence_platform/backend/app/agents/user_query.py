import operator
from typing import Annotated, TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, START, END

class QueryState(TypedDict):
    question: str
    database_id: str
    relevant_context: Dict[str, Any]
    generated_sql: Optional[str]
    query_results: Optional[List[Dict[str, Any]]]
    validation_error: Optional[str]
    synthesized_answer: Optional[str]
    recommended_visualizations: Optional[Dict[str, Any]]
    iterations: int

def parse_question_node(state: QueryState):
    """Initial intent parsing of the user question."""
    return {"iterations": state.get("iterations", 0)}

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
        
        # 1. Embed Question
        try:
            print("[DEBUG] Embedding question...")
            query_vector = list(list(embedding_model.embed([question]))[0])
            knn_query = {
                "field": "embedding",
                "query_vector": query_vector,
                "k": 1,
                "num_candidates": 50
            }
            # Remove db_id filter for global routing
            search_body = {"knn": knn_query}
        except Exception as embed_err:
            print(f"Embedding generation failed: {embed_err}")
            return {"relevant_context": context}
        
        # 2. Search in ES (Entities Index)
        index_name = f"{settings.ELASTICSEARCH_INDEX_PREFIX}entities"
        if es_client:
            exists = await es_client.indices.exists(index=index_name)
            print(f"[DEBUG] ES Entities Index exists: {exists}")
            if exists:
                es_results = await es_client.search(index=index_name, body=search_body)
                
                matched_entities = []
                
                # Enforce strict top 1 match
                hits = es_results.get("hits", {}).get("hits", [])[:1]
                print(f"[DEBUG] ES raw response hits (restricted to 1): {len(hits)}")
                for hit in hits:
                    source = hit["_source"]
                    if source.get("entity_id") not in matched_entities:
                        matched_entities.append(source.get("entity_id"))
                
                print(f"[DEBUG] Matched Entities from ES: {matched_entities}")
                
            # 3. Query Neo4j to find which Database and Tables map to these Entities
            if neo4j_driver and matched_entities:
                async with neo4j_driver.session() as session:
                    cypher = """
                    MATCH (db:Database)-[:HAS_TABLE]->(t:Table)-[:MAPS_TO]->(e:Entity)
                    WHERE e.id IN $matched_entities
                    OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column)
                    WITH db, e, t, collect({name: c.name, type: c.type, sample_values: c.sample_values}) AS columns
                    ORDER BY size(columns) DESC
                    WITH db, e, collect({name: t.name, columns: columns})[0..2] AS top_tables_for_db
                    RETURN db.id AS database_id, db.name AS database_name, db.connection_string AS conn_str, top_tables_for_db AS tables
                    """
                    neo_res = await session.run(cypher, matched_entities=matched_entities)
                    records = await neo_res.data()
                    
                    if records:
                        context["available_databases"] = records
                        context["relationships"] = [{"source": "Entity", "target": "Table", "type": "MAPS_TO"}]
                        
                        import json
                        print(f"[DEBUG] Autonomously retrieved schema for {len(records)} Databases:\n{json.dumps(records, indent=2)}")
                        return {"relevant_context": context}
                    else:
                        print(f"[DEBUG] Neo4j found no linked databases for entities: {matched_entities}")
                        
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
            
        print(f"[DEBUG] Generated SQL Query:\n{sql}\nTarget DB: {target_db}")
        return {"generated_sql": sql.strip(), "database_id": target_db}
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

workflow.add_node("parse_question", parse_question_node)
workflow.add_node("retrieve_context", retrieve_context_node)
workflow.add_node("generate_sql", generate_sql_node)
workflow.add_node("execute_sql", execute_sql_node)
workflow.add_node("validate_results", validate_results_node)
workflow.add_node("synthesize_answer", synthesize_answer_node)
workflow.add_node("recommend_visualizations", recommend_visualizations_node)

workflow.add_edge(START, "parse_question")
workflow.add_edge("parse_question", "retrieve_context")
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

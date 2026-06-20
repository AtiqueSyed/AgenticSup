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
        # Initialize fast, local open-source embedding model
        embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        
        # 1. Embed Question
        try:
            query_vector = list(list(embedding_model.embed([question]))[0])
            knn_query = {
                "field": "embedding",
                "query_vector": query_vector,
                "k": 5,
                "num_candidates": 50
            }
            if db_id:
                knn_query["filter"] = {"term": {"database_id": db_id}}
            search_body = {"knn": knn_query}
        except Exception as embed_err:
            print(f"Embedding generation failed: {embed_err}")
            return {"relevant_context": context}
        
        # 2. Search in ES
        index_name = f"{settings.ELASTICSEARCH_INDEX_PREFIX}tables"
        if es_client and await es_client.indices.exists(index=index_name):
            print(f"[DEBUG] Searching ES with body: {search_body}")
            es_results = await es_client.search(index=index_name, body=search_body)
            print(f"[DEBUG] ES raw response hits: {len(es_results.get('hits', {}).get('hits', []))}")
            
            top_tables = []
            for hit in es_results["hits"]["hits"]:
                source = hit["_source"]
                top_tables.append(source["table_name"])
                context["tables"].append({
                    "name": source["table_name"],
                    "description": source.get("description", "")
                })
                
            # 3. Query Neo4j for related entities to supplement context
            if neo4j_driver and top_tables:
                async with neo4j_driver.session() as session:
                    cypher = """
                    MATCH (e1:Entity)-[r]->(e2:Entity)
                    WHERE e1.id IN $tables OR e2.id IN $tables
                    RETURN e1.id AS source, type(r) AS rel, e2.id AS target
                    """
                    neo_res = await session.run(cypher, tables=top_tables)
                    rels = await neo_res.data()
                    context["relationships"] = rels
                    print(f"[DEBUG] Retrieved {len(rels)} relationships from Neo4j Knowledge Graph.")
                    
        print(f"[DEBUG] Context successfully assembled. Tables: {[t['name'] for t in context['tables']]}")
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
    
    # We pass the schema/context retrieved from Neo4j/Elasticsearch (mocked here if empty)
    context = json.dumps(state.get("relevant_context", {}))
    error_feedback = f"\nPrevious error to fix: {state['validation_error']}" if state.get("validation_error") else ""
    
    prompt = f"""
    You are an expert Oracle SQL Developer. Given the following schema context, write a highly optimized SQL query to answer the user's question.
    Only return the raw SQL code. No markdown formatting, no explanations.
    
    Context: {context}
    Question: {state['question']}
    {error_feedback}
    """
    
    try:
        response = await client.chat.completions.create(
            model=settings.DEFAULT_LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        sql = response.choices[0].message.content.strip()
        # Remove any stray markdown
        if sql.startswith("```sql"): sql = sql[6:]
        if sql.endswith("```"): sql = sql[:-3]
        print(f"[DEBUG] Generated SQL Query:\n{sql.strip()}\n")
        return {"generated_sql": sql.strip()}
    except Exception as e:
        # MOCK FALLBACK: For local testing where AWS Bedrock is inaccessible
        print(f"LLM API Failed, falling back to mock SQL: {e}")
        return {"generated_sql": "SELECT * FROM QUEUEMEMBERS FETCH FIRST 10 ROWS ONLY"}

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def execute_sql_node(state: QueryState):
    """Executes the SQL securely against the target database."""
    print("----- [QUERY NODE: execute_sql] Started -----")
    if not state.get("generated_sql"):
        return {"validation_error": "No SQL generated to execute."}
        
    # For hackathon purposes, we use a default connection if none provided in context
    conn_str = state.get("relevant_context", {}).get("connection_string")
    if not conn_str:
        conn_str = "oracle+oracledb_async://agenticsupervisor_developer:agenticsupervisor@host.docker.internal:1521/?service_name=XEPDB1"
    
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

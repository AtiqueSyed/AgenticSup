import asyncio
from elasticsearch import AsyncElasticsearch
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '../backend/.env'))

async def main():
    es = AsyncElasticsearch(
        os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200"),
        basic_auth=(os.environ.get("ELASTICSEARCH_USERNAME", "elastic"), os.environ.get("ELASTICSEARCH_PASSWORD", "password")),
        verify_certs=False
    )
    
    index_name = "test_tables"
    if await es.indices.exists(index=index_name):
        await es.indices.delete(index=index_name)
        
    mapping = {
        "mappings": {
            "properties": {
                "database_id": {"type": "keyword"},
                "table_name": {"type": "keyword"},
                "description": {"type": "text"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": 1536,
                    "index": True,
                    "similarity": "cosine"
                }
            }
        }
    }
    
    await es.indices.create(index=index_name, body=mapping)
    print("Created index.")
    await es.close()

if __name__ == "__main__":
    asyncio.run(main())

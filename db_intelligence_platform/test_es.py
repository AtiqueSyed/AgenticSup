import asyncio
from elasticsearch import AsyncElasticsearch
async def main():
    es = AsyncElasticsearch('http://localhost:9200', basic_auth=('elastic', 'oZ1npMQ5_TYwAxi2LfEe'))
    search_body = {
        'knn': {
            'field': 'embedding',
            'query_vector': [0.01]*384,
            'k': 5,
            'num_candidates': 50,
            'filter': {'term': {'database_id': 'd53cd0cbfa2de72bdd83c5261af58c88'}}
        }
    }
    print('Testing body=search_body')
    res1 = await es.search(index='hackathon-agentic.supervisor-tables', body=search_body)
    h1 = res1.get('hits', {}).get('hits', [])
    print(f'Body hits: {len(h1)}')
    print('Testing knn=search_body[knn]')
    res2 = await es.search(index='hackathon-agentic.supervisor-tables', knn=search_body['knn'])
    h2 = res2.get('hits', {}).get('hits', [])
    print(f'KNN hits: {len(h2)}')
    await es.close()
asyncio.run(main())


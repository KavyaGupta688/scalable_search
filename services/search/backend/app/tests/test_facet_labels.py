import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from sqlalchemy import text
from modules.shared.integration import database_engine


@pytest.mark.asyncio
async def test_dataset_facet_preserves_identity_and_connector_label(search_headers, canonical_file_id):
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test',
                           headers=search_headers, timeout=60) as client:
        detail = await client.get('/files/' + canonical_file_id)
        assert detail.status_code == 200
        file = detail.json()
        with database_engine('search').connect() as connection:
            dataset_id = connection.execute(text('SELECT dataset_id FROM file_metadata WHERE file_id=:id'),
                                            {'id': canonical_file_id}).scalar_one()
        response = await client.post('/search', json={
            'query': '*', 'search_mode': 'text',
            'filters': {'dataset_ids': [dataset_id]}, 'limit': 100,
        })
        assert response.status_code == 200
        data = response.json()
        assert data['facets']['datasets'] == [{
            'value': dataset_id, 'label': file['dataset_name'],
            'count': data['total'],
        }]
        assert all(row['dataset_id'] == dataset_id for row in data['results'])


@pytest.mark.asyncio
async def test_exact_totals_on_empty_pages_and_facets_match_current_visible_rows(search_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test', headers=search_headers) as client:
        first = (await client.post('/search', json={'query':'*','search_mode':'text','limit':1})).json()
        assert first['total'] > 0
        beyond = (await client.post('/search', json={'query':'*','search_mode':'text','offset':first['total']+1,'limit':1})).json()
        assert beyond['results'] == []
        assert beyond['total'] == first['total'] == beyond['facets']['total_matches']
        from modules.shared.catalog import VISIBLE_SQL
        with database_engine('search').connect() as c:
            for facet, column in [('file_types','file_type'),('categories','category'),('ai_generated','ai_generated'),('pii_detected','pii_detected')]:
                rows = c.execute(text(f'SELECT {column},count(*) FROM file_metadata WHERE {VISIBLE_SQL} AND {column} IS NOT NULL GROUP BY {column}')).all()
                expected = {str(value).lower() if isinstance(value,bool) else str(value):count for value,count in rows}
                assert {x['value']:x['count'] for x in first['facets'][facet]} == expected

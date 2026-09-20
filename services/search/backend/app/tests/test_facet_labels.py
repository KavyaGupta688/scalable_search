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

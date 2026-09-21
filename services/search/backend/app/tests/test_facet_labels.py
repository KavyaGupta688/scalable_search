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
async def test_file_type_facet_keeps_every_type_when_a_type_is_selected(search_headers, canonical_file_id):
    with database_engine('search').connect() as connection:
        file_type = connection.execute(text('SELECT file_type FROM file_metadata WHERE file_id=:id'),
                                       {'id': canonical_file_id}).scalar_one()
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test',
                           headers=search_headers, timeout=60) as client:
        everything = (await client.post('/search', json={
            'query': '*', 'search_mode': 'text', 'limit': 1})).json()
        selected = (await client.post('/search', json={
            'query': '*', 'search_mode': 'text', 'limit': 1,
            'filters': {'file_types': [file_type]}})).json()
    counts = {row['value']: row['count'] for row in selected['facets']['file_types']}
    # Selecting a type narrows the results but not the per-type counts.
    assert sum(counts.values()) == everything['total']
    assert selected['total'] == counts[file_type]

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_text_search_endpoint(search_headers, canonical_file_id):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=search_headers
    ) as client:
        from sqlalchemy import text
        from modules.shared.integration import database_engine
        with database_engine('search').connect() as c:
            filename = c.execute(text('SELECT file_name FROM file_metadata WHERE file_id=:id'), {'id':canonical_file_id}).scalar_one()
        response = await client.get("/search/text", params={'q':filename})
        assert response.status_code == 200
        data = response.json()
        assert data["search_mode"] == "text"
        assert data["total"] > 0
        assert len(data["results"]) > 0
        assert canonical_file_id in {row['file_id'] for row in data['results']}

        # Verify result item schema
        first_item = data["results"][0]
        assert "file_id" in first_item
        assert "title" in first_item
        assert "score_info" in first_item
        assert "keyword" in first_item["score_info"]["match_sources"]


@pytest.mark.asyncio
async def test_text_search_with_filter(search_headers, canonical_file_id):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=search_headers
    ) as client:
        response = await client.get("/search/text?q=acceptance&file_type=image")
        assert response.status_code == 200
        data = response.json()
        for res in data["results"]:
            assert res["file_type"] == "image"

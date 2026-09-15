import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_text_search_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/search/text?q=mining")
        assert response.status_code == 200
        data = response.json()
        assert data["search_mode"] == "text"
        assert data["total"] > 0
        assert len(data["results"]) > 0
        
        # Verify result item schema
        first_item = data["results"][0]
        assert "file_id" in first_item
        assert "title" in first_item
        assert "score_info" in first_item
        assert "keyword" in first_item["score_info"]["match_sources"]

@pytest.mark.asyncio
async def test_text_search_with_filter():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/search/text?q=mineral&file_type=image")
        assert response.status_code == 200
        data = response.json()
        for res in data["results"]:
            assert res["file_type"] == "image"

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_similar_search_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Request similar files to lithium mineral scan
        payload = {
            "file_id": "file_geo_001",
            "limit": 5
        }
        response = await client.post("/search/similar", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["search_mode"] == "similar"
        assert len(data["results"]) > 0
        
        # Verify original file_geo_001 is excluded from similar results
        for item in data["results"]:
            assert item["file_id"] != "file_geo_001"

@pytest.mark.asyncio
async def test_file_details_preview_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/files/file_geo_001")
        assert response.status_code == 200
        data = response.json()
        assert data["file_id"] == "file_geo_001"
        assert "technical" in data
        assert "ai_enrichment" in data
        assert data["ai_enrichment"]["caption"] is not None

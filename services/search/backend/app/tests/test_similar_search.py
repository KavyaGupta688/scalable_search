import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_similar_search_endpoint(search_headers, canonical_file_id):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=search_headers
    ) as client:
        # Request similar files to lithium acceptance scan
        payload = {"file_id": canonical_file_id, "limit": 5}
        response = await client.post("/search/similar", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["search_mode"] == "similar"
        assert len(data["results"]) > 0

        # Verify original file_geo_001 is excluded from similar results
        for item in data["results"]:
            assert item["file_id"] != canonical_file_id


@pytest.mark.asyncio
async def test_file_details_preview_endpoint(search_headers, canonical_file_id):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=search_headers
    ) as client:
        response = await client.get("/files/" + canonical_file_id)
        assert response.status_code == 200
        data = response.json()
        assert data["file_id"] == canonical_file_id
        assert "technical" in data
        assert "ai_enrichment" in data
        assert "caption" in data["ai_enrichment"]
        assert data["description"]

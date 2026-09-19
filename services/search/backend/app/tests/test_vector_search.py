import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_vector_search_endpoint(search_headers, canonical_file_id):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=search_headers
    ) as client:
        payload = {"query": "acceptance", "limit": 5}
        response = await client.post("/search/vector", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["search_mode"] == "vector"
        assert len(data["results"]) > 0

        # Verify vector similarity score presence
        first_item = data["results"][0]
        assert first_item["score_info"]["vector_similarity"] is not None
        assert "vector" in first_item["score_info"]["match_sources"]

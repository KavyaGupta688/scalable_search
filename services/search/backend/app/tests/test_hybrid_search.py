import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_hybrid_search_rrf_endpoint(search_headers, canonical_file_id):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=search_headers
    ) as client:
        payload = {
            "query": "acceptance",
            "search_mode": "hybrid",
            "rrf_k": 60,
            "keyword_weight": 0.5,
            "vector_weight": 0.5,
            "limit": 10,
        }
        response = await client.post("/search", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["search_mode"] == "hybrid"
        assert data["total"] > 0
        assert len(data["results"]) > 0

        # Verify RRF score is computed
        top_result = data["results"][0]
        assert top_result["score_info"]["rrf_score"] > 0
        assert data["facets"] is not None
        assert len(data["facets"]["file_types"]) > 0


@pytest.mark.asyncio
async def test_facets_endpoint(search_headers, canonical_file_id):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=search_headers
    ) as client:
        response = await client.get("/search/facets?q=acceptance")
        assert response.status_code == 200
        data = response.json()
        assert "file_types" in data
        assert "categories" in data
        assert "datasets" in data
        assert "total_matches" in data

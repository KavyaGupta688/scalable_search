import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_trending_searches_endpoint(search_headers, canonical_file_id):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=search_headers
    ) as client:
        response = await client.get("/search/trending")
        assert response.status_code == 200
        data = response.json()
        assert "trending" in data
        assert len(data["trending"]) > 0
        assert data["trending"][0]["query"] is not None


@pytest.mark.asyncio
async def test_suggestions_endpoint(search_headers, canonical_file_id):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=search_headers
    ) as client:
        response = await client.get("/search/suggestions?q=accept")
        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        assert len(data["suggestions"]) > 0


@pytest.mark.asyncio
async def test_popular_datasets_endpoint(search_headers, canonical_file_id):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=search_headers
    ) as client:
        response = await client.get("/datasets/popular")
        assert response.status_code == 200
        data = response.json()
        assert "datasets" in data
        assert len(data["datasets"]) > 0
        assert data["datasets"][0]["popularity_score"] > 0


@pytest.mark.asyncio
async def test_events_and_download_export(search_headers, canonical_file_id):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=search_headers
    ) as client:
        # Record search event
        event_res = await client.post(
            "/events/search",
            json={"event_type": "SEARCH", "query": "acceptance", "result_count": 5},
        )
        assert event_res.status_code == 201

        # Batch export download
        export_res = await client.post(
            "/events/export-download",
            json={
                "selected_file_ids": [canonical_file_id, canonical_file_id],
                "bundle_metadata_csv": True,
                "search_query": "acceptance",
            },
        )
        assert export_res.status_code == 410
        assert "/downloads/batch" in export_res.json()["detail"]

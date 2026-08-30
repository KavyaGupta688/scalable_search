import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_trending_searches_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/search/trending")
        assert response.status_code == 200
        data = response.json()
        assert "trending" in data
        assert len(data["trending"]) > 0
        assert data["trending"][0]["query"] is not None

@pytest.mark.asyncio
async def test_suggestions_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/search/suggestions?q=sat")
        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        assert len(data["suggestions"]) > 0

@pytest.mark.asyncio
async def test_popular_datasets_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/datasets/popular")
        assert response.status_code == 200
        data = response.json()
        assert "datasets" in data
        assert len(data["datasets"]) > 0
        assert data["datasets"][0]["popularity_score"] > 0

@pytest.mark.asyncio
async def test_events_and_download_export():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Record search event
        event_res = await client.post("/events/search", json={
            "event_type": "SEARCH",
            "query": "geological mineral scan",
            "result_count": 5
        })
        assert event_res.status_code == 201
        
        # Batch export download
        export_res = await client.post("/events/export-download", json={
            "selected_file_ids": ["file_geo_001", "file_sat_001"],
            "bundle_metadata_csv": True,
            "search_query": "geological mineral scan"
        })
        assert export_res.status_code == 200
        data = export_res.json()
        assert data["status"] == "SUBMITTED_TO_DOWNLOAD_AUDIT"
        assert data["total_files"] == 2
        assert "metadata.csv" in data["metadata_bundle"]

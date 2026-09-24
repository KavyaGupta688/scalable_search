import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_hybrid_search_rrf_endpoint(search_headers, canonical_file_id, canonical_title):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=search_headers
    ) as client:
        payload = {
            "query": canonical_title,
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
async def test_facets_endpoint(search_headers, canonical_file_id, canonical_title):
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


@pytest.mark.asyncio
async def test_hybrid_filters_apply_and_counts_match_results(search_headers, canonical_file_id, canonical_title):
    from sqlalchemy import text
    from modules.shared.integration import database_engine

    with database_engine("search").connect() as connection:
        file_type = connection.execute(
            text("SELECT file_type FROM file_metadata WHERE file_id=:id"),
            {"id": canonical_file_id},
        ).scalar_one()
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=search_headers, timeout=60
    ) as client:
        response = await client.post(
            "/search",
            json={
                "query": canonical_title,
                "search_mode": "hybrid",
                "filters": {"file_types": [file_type]},
                "limit": 100,
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Filters constrain both retrievers, and the counts describe the returned set.
        assert all(item["file_type"] == file_type for item in data["results"])
        assert data["total"] == len(data["results"]) == data["facets"]["total_matches"]


@pytest.mark.asyncio
async def test_resolution_filter_validates_tiers_and_keeps_counts_consistent(search_headers, canonical_file_id, canonical_title):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=search_headers, timeout=60
    ) as client:
        rejected = await client.post(
            "/search", json={"query": "*", "search_mode": "text", "filters": {"resolutions": ["8k"]}}
        )
        assert rejected.status_code == 422

        everything = (await client.post(
            "/search", json={"query": "*", "search_mode": "text", "limit": 100}
        )).json()
        # Catalog-wide tier counts: never more photos/videos than files.
        tiers = {row["value"]: row["count"] for row in everything["facets"]["resolutions"]}
        assert sum(tiers.values()) <= everything["total"]

        for tier in list(tiers)[:3]:
            response = await client.post(
                "/search",
                json={"query": "*", "search_mode": "text", "limit": 100, "filters": {"resolutions": [tier]}},
            )
            assert response.status_code == 200
            data = response.json()
            # Selecting a tier narrows the results but every tier keeps its count.
            assert data["total"] == tiers[tier]
            assert {r["value"]: r["count"] for r in data["facets"]["resolutions"]} == tiers


@pytest.mark.asyncio
async def test_download_plan_follows_search_order_and_reports_size(search_headers, canonical_file_id, canonical_title):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=search_headers, timeout=60
    ) as client:
        results = (await client.post(
            "/search", json={"query": "*", "search_mode": "text", "limit": 100}
        )).json()
        plan = (await client.post(
            "/search/download-plan",
            json={"query": "*", "search_mode": "text", "count": 3, "include_ids": True},
        )).json()
        assert plan["total_matches"] == results["total"]
        assert plan["count"] == len(plan["file_ids"]) <= 3
        # The top N are the first N downloadable files of the results list, in that order.
        limit = plan["limits"]["max_file_bytes"]
        downloadable = [r for r in results["results"] if not limit or r["file_size"] <= limit]
        assert plan["file_ids"] == [r["file_id"] for r in downloadable][: plan["count"]]
        assert plan["total_bytes"] == sum(r["file_size"] for r in downloadable[: plan["count"]])
        # Ids are only returned when asked for.
        bare = (await client.post(
            "/search/download-plan", json={"query": "*", "search_mode": "text", "count": 3}
        )).json()
        assert "file_ids" not in bare


@pytest.mark.asyncio
async def test_size_filter_validates_and_keeps_bucket_counts(search_headers, canonical_file_id, canonical_title):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=search_headers, timeout=60
    ) as client:
        rejected = await client.post(
            "/search", json={"query": "*", "search_mode": "text", "filters": {"size_buckets": ["huge"]}}
        )
        assert rejected.status_code == 422
        everything = (await client.post(
            "/search", json={"query": "*", "search_mode": "text", "limit": 100}
        )).json()
        buckets = {row["value"]: row["count"] for row in everything["facets"]["sizes"]}
        assert sum(buckets.values()) == everything["total"]  # every file is in exactly one bucket
        for bucket in list(buckets)[:2]:
            data = (await client.post(
                "/search",
                json={"query": "*", "search_mode": "text", "limit": 100, "filters": {"size_buckets": [bucket]}},
            )).json()
            assert data["total"] == buckets[bucket]
            assert {r["value"]: r["count"] for r in data["facets"]["sizes"]} == buckets

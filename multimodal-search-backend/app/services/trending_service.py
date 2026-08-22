import json
import logging
from typing import List, Dict, Any
from datetime import datetime, timezone
from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.search import TrendingItem, TrendingResponse, SuggestionItem, SuggestionsResponse
from app.db.redis import get_cache_client
from app.utils.query_normalizer import normalize_text

logger = logging.getLogger(__name__)

CACHE_KEY_TRENDING = "cache:trending_searches"
CACHE_TTL_TRENDING = 120  # 2 minutes

# Curated fallback trending queries matching multimodal domain
DEFAULT_TRENDING = [
    {"query": "Satellite Earth Observation", "count": 142, "category": "Vehicles", "score": 98.4},
    {"query": "Geological Survey & Mineral Scans", "count": 128, "category": "Nature", "score": 92.1},
    {"query": "Industrial Safety & Equipment", "count": 115, "category": "Technology", "score": 88.5},
    {"query": "Autonomous Vehicle Road Telemetry", "count": 94, "category": "Vehicles", "score": 81.2},
    {"query": "Medical Pathology & Diagnostics", "count": 89, "category": "Medical", "score": 79.0},
    {"query": "Renewable Energy Turbine Logs", "count": 76, "category": "Technology", "score": 72.4},
    {"query": "Urban Architecture 3D Scans", "count": 68, "category": "Architecture", "score": 67.8},
    {"query": "Wildlife Biodiversity Tracking", "count": 55, "category": "Animals", "score": 60.1},
]

class TrendingService:
    def __init__(self, analytics_repo: AnalyticsRepository):
        self.analytics_repo = analytics_repo

    async def get_trending(self, limit: int = 8) -> TrendingResponse:
        cache = await get_cache_client()
        cached = await cache.get(CACHE_KEY_TRENDING)

        if cached:
            try:
                data = json.loads(cached)
                return TrendingResponse(**data)
            except Exception:
                pass

        # Query analytics repo for recent counts
        db_trending = await self.analytics_repo.get_trending_queries(hours=24, limit=limit)
        
        items: List[TrendingItem] = []
        if db_trending:
            for idx, item in enumerate(db_trending):
                items.append(
                    TrendingItem(
                        query=item["query"].title(),
                        search_count=item["count"],
                        category="Trending",
                        trending_score=round(max(10.0, 100.0 - (idx * 10)), 1)
                    )
                )

        # Fallback to default trending if DB has few queries
        if len(items) < 4:
            existing_queries = {i.query.lower() for i in items}
            for d in DEFAULT_TRENDING:
                if d["query"].lower() not in existing_queries and len(items) < limit:
                    items.append(
                        TrendingItem(
                            query=d["query"],
                            search_count=d["count"],
                            category=d["category"],
                            trending_score=d["score"]
                        )
                    )

        response = TrendingResponse(
            time_window="last_24_hours",
            trending=items,
            generated_at=datetime.now(timezone.utc)
        )

        try:
            await cache.set(CACHE_KEY_TRENDING, response.model_dump_json(), ex=CACHE_TTL_TRENDING)
        except Exception as e:
            logger.warning(f"Failed to cache trending: {e}")

        return response

    async def get_suggestions(self, query: str, limit: int = 10) -> SuggestionsResponse:
        norm_q = normalize_text(query)
        if not norm_q:
            return SuggestionsResponse(query=query, suggestions=[], total=0)

        trending_resp = await self.get_trending(limit=15)
        suggestions: List[SuggestionItem] = []
        seen = set()

        # 1. Match trending searches
        for item in trending_resp.trending:
            if norm_q in item.query.lower():
                if item.query.lower() not in seen:
                    suggestions.append(SuggestionItem(text=item.query, type="trending", badge="🔥 Trending"))
                    seen.add(item.query.lower())

        # 2. Match standard categories
        categories = [
            "People", "Nature", "Architecture", "Technology", "Animals", "Medical",
            "Vehicles", "Food", "Sports", "Abstract", "Business", "Education"
        ]
        for cat in categories:
            if norm_q in cat.lower():
                if cat.lower() not in seen:
                    suggestions.append(SuggestionItem(text=cat, type="category", badge="📁 Category"))
                    seen.add(cat.lower())

        # 3. Match frequent domain tags
        tags = [
            "satellite", "infrared", "geology", "mineral", "mining", "drilling",
            "turbine", "sensor", "pathology", "radiology", "diagnostics",
            "drone", "thermal", "blueprint", "seismic", "biodiversity",
            "neural", "synthetic", "telemetry", "spectrometry", "audio-transcript"
        ]
        for tag in tags:
            if norm_q in tag.lower():
                if tag.lower() not in seen:
                    suggestions.append(SuggestionItem(text=tag.title(), type="tag", badge="🏷️ Tag"))
                    seen.add(tag.lower())

        return SuggestionsResponse(
            query=query,
            suggestions=suggestions[:limit],
            total=len(suggestions[:limit])
        )

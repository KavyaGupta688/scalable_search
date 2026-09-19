import json
import logging
from typing import List, Dict, Any
from datetime import datetime, timezone
from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.search import (
    TrendingItem,
    TrendingResponse,
    SuggestionItem,
    SuggestionsResponse,
)
from app.db.redis import get_cache_client
from app.utils.query_normalizer import normalize_text

logger = logging.getLogger(__name__)

CACHE_KEY_TRENDING = "cache:trending_searches"
CACHE_TTL_TRENDING = 120  # 2 minutes


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
        db_trending = await self.analytics_repo.get_trending_queries(
            hours=24, limit=limit
        )

        items: List[TrendingItem] = []
        if db_trending:
            for idx, item in enumerate(db_trending):
                items.append(
                    TrendingItem(
                        query=item["query"].title(),
                        search_count=item["count"],
                        category="Trending",
                        trending_score=round(max(10.0, 100.0 - (idx * 10)), 1),
                    )
                )

        response = TrendingResponse(
            time_window="last_24_hours",
            trending=items,
            generated_at=datetime.now(timezone.utc),
        )

        try:
            await cache.set(
                CACHE_KEY_TRENDING, response.model_dump_json(), ex=CACHE_TTL_TRENDING
            )
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
                    suggestions.append(
                        SuggestionItem(
                            text=item.query, type="trending", badge="🔥 Trending"
                        )
                    )
                    seen.add(item.query.lower())

        from sqlalchemy import text
        from modules.shared.catalog import VISIBLE_SQL

        rows = await self.analytics_repo.db.execute(
            text(
                "SELECT DISTINCT title AS value FROM file_metadata WHERE "
                + VISIBLE_SQL
                + " AND title ILIKE :prefix ORDER BY value LIMIT :limit"
            ),
            {"prefix": norm_q + "%", "limit": limit},
        )
        for row in rows:
            if row.value.lower() not in seen:
                suggestions.append(SuggestionItem(text=row.value, type="file"))
                seen.add(row.value.lower())
        suggestions = suggestions[:limit]
        return SuggestionsResponse(
            query=query, suggestions=suggestions, total=len(suggestions)
        )

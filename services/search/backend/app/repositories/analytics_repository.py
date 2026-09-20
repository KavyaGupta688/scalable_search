from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timezone, timedelta
from app.models.search_event import SearchEvent


class AnalyticsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_event(
        self,
        event_type: str,
        user_id: str,
        user_role: str,
        file_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        query: Optional[str] = None,
        normalized_query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        result_count: int = 0,
        meta_info: Optional[Dict[str, Any]] = None,
        execution_time_ms: int = 0,
    ) -> SearchEvent:
        event = SearchEvent(
            event_type=event_type,
            user_id=user_id,
            user_role=user_role,
            file_id=file_id,
            dataset_id=dataset_id,
            query=query,
            normalized_query=normalized_query,
            filters=filters,
            result_count=result_count,
            meta_info=meta_info,
        )
        self.db.add(event)
        await self.db.flush()
        from modules.shared.delivery import enqueue_async

        await enqueue_async(
            self.db,
            "audit:" + str(event.id),
            "audit",
            {
                "event_id": "search-" + str(event.id),
                "action": event_type,
                "actor": user_id,
                "user_role": user_role,
                "entity_type": "search",
                "entity_id": file_id or dataset_id or "query",
                "execution_time_ms": execution_time_ms,
                "metadata": {"query": query, "result_count": result_count},
            },
        )
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def get_trending_queries(
        self, hours: int = 24, limit: int = 10
    ) -> List[Dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        stmt = (
            select(
                SearchEvent.normalized_query,
                func.count(SearchEvent.id).label("search_count"),
            )
            .where(
                SearchEvent.event_type == "SEARCH",
                SearchEvent.created_at >= cutoff,
                SearchEvent.normalized_query.isnot(None),
                func.length(SearchEvent.normalized_query) > 2,
            )
            .group_by(SearchEvent.normalized_query)
            .order_by(desc("search_count"))
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        rows = res.all()
        return [{"query": r[0], "count": r[1]} for r in rows]

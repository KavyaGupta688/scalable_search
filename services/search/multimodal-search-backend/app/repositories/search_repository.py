from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models.search_event import SearchEvent

class SearchRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_search(
        self,
        query: str,
        normalized_query: str,
        user_id: str,
        user_role: str,
        filters: Optional[Dict[str, Any]],
        result_count: int
    ) -> SearchEvent:
        event = SearchEvent(
            event_type="SEARCH",
            query=query,
            normalized_query=normalized_query,
            user_id=user_id,
            user_role=user_role,
            filters=filters,
            result_count=result_count
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def get_recent_searches(self, limit: int = 50) -> List[SearchEvent]:
        stmt = select(SearchEvent).where(SearchEvent.event_type == "SEARCH").order_by(desc(SearchEvent.created_at)).limit(limit)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

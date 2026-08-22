from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, update
from app.models.dataset import Dataset

class DatasetRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, dataset_id: str) -> Optional[Dataset]:
        stmt = select(Dataset).where(Dataset.id == dataset_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, limit: int = 50) -> List[Dataset]:
        stmt = select(Dataset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_popular_datasets(self, limit: int = 10) -> List[Dataset]:
        stmt = select(Dataset).order_by(desc(Dataset.popularity_score), desc(Dataset.view_count)).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def increment_view(self, dataset_id: str):
        stmt = update(Dataset).where(Dataset.id == dataset_id).values(
            view_count=Dataset.view_count + 1,
            popularity_score=Dataset.popularity_score + 1.0
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def increment_download(self, dataset_id: str, count: int = 1):
        stmt = update(Dataset).where(Dataset.id == dataset_id).values(
            download_count=Dataset.download_count + count,
            popularity_score=Dataset.popularity_score + (count * 2.0)
        )
        await self.db.execute(stmt)
        await self.db.commit()

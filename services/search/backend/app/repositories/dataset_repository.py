from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import bindparam, func, text, select, desc, update
from app.models.dataset import Dataset
from app.models.search_event import SearchEvent
from modules.shared.catalog import VISIBLE_SQL
from sqlalchemy.orm.attributes import set_committed_value


class DatasetRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, dataset_id: str) -> Optional[Dataset]:
        stmt = (
            select(Dataset)
            .where(
                text(
                    "EXISTS (SELECT 1 FROM file_metadata WHERE file_metadata.dataset_id=datasets.id AND "
                    + VISIBLE_SQL
                    + ")"
                )
            )
            .where(Dataset.id == dataset_id)
        )
        result = await self.db.execute(stmt)
        dataset = result.scalar_one_or_none()
        if dataset:
            await self._visible_counts([dataset])
        return dataset

    async def get_all(self, limit: int = 50) -> List[Dataset]:
        stmt = (
            select(Dataset)
            .where(
                text(
                    "EXISTS (SELECT 1 FROM file_metadata WHERE file_metadata.dataset_id=datasets.id AND "
                    + VISIBLE_SQL
                    + ")"
                )
            )
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        datasets = list(result.scalars().all())
        await self._visible_counts(datasets)
        return datasets

    async def get_popular_datasets(self, limit: int = 10) -> List[Dataset]:
        stmt = (
            select(Dataset)
            .where(
                text(
                    "EXISTS (SELECT 1 FROM file_metadata WHERE file_metadata.dataset_id=datasets.id AND "
                    + VISIBLE_SQL
                    + ")"
                )
            )
            .order_by(desc(Dataset.popularity_score), desc(Dataset.view_count))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        datasets = list(result.scalars().all())
        await self._visible_counts(datasets)
        await self._recent_views(datasets)
        return datasets

    async def _visible_counts(self, datasets):
        # Counts must use current entitlements, not stale projection aggregates.
        if not datasets:
            return
        # Only the requested datasets are counted; scanning every dataset's files
        # on each call does not scale with catalog size.
        result = await self.db.execute(
            text(
                "SELECT dataset_id, count(*) AS files, coalesce(sum(file_size),0) AS bytes "
                "FROM file_metadata WHERE dataset_id IN :ids AND "
                + VISIBLE_SQL
                + " GROUP BY dataset_id"
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": [str(d.id) for d in datasets]},
        )
        counts = {str(r.dataset_id): (r.files, r.bytes) for r in result}
        for dataset in datasets:
            files, size = counts.get(str(dataset.id), (0, 0))
            set_committed_value(dataset, "file_count", files)
            set_committed_value(dataset, "total_size_bytes", size)

    async def _recent_views(self, datasets, days: int = 7):
        """Attaches the number of DATASET_OPEN events in the last `days` days."""
        if not datasets:
            return
        rows = await self.db.execute(
            select(SearchEvent.dataset_id, func.count(SearchEvent.id))
            .where(
                SearchEvent.event_type == "DATASET_OPEN",
                SearchEvent.dataset_id.in_([str(d.id) for d in datasets]),
                SearchEvent.created_at
                >= datetime.now(timezone.utc) - timedelta(days=days),
            )
            .group_by(SearchEvent.dataset_id)
        )
        views = {str(dataset_id): count for dataset_id, count in rows}
        for dataset in datasets:
            # Transient (unmapped) attribute read by DatasetSummary.
            dataset.view_count_7d = views.get(str(dataset.id), 0)

    async def increment_view(self, dataset_id: str):
        stmt = (
            update(Dataset)
            .where(Dataset.id == dataset_id)
            .values(
                view_count=Dataset.view_count + 1,
                popularity_score=Dataset.popularity_score + 1.0,
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def increment_download(self, dataset_id: str, count: int = 1):
        stmt = (
            update(Dataset)
            .where(Dataset.id == dataset_id)
            .values(
                download_count=Dataset.download_count + count,
                popularity_score=Dataset.popularity_score + (count * 2.0),
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()

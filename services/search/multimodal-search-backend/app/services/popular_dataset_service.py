import json
import logging
from typing import List
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.dataset import DatasetSummary, PopularDatasetsResponse
from app.db.redis import get_cache_client

logger = logging.getLogger(__name__)

CACHE_KEY_POPULAR_DATASETS = "cache:popular_datasets"
CACHE_TTL_SECONDS = 300  # 5 minutes

class PopularDatasetService:
    def __init__(self, dataset_repo: DatasetRepository):
        self.dataset_repo = dataset_repo

    async def get_popular_datasets(self, limit: int = 8) -> PopularDatasetsResponse:
        cache = await get_cache_client()
        cached = await cache.get(CACHE_KEY_POPULAR_DATASETS)
        
        if cached:
            try:
                data = json.loads(cached)
                return PopularDatasetsResponse(**data)
            except Exception as e:
                logger.warning(f"Failed to parse cached popular datasets: {e}")

        # Fetch from DB and rank
        datasets = await self.dataset_repo.get_popular_datasets(limit=limit)
        summaries = [DatasetSummary.model_validate(d) for d in datasets]
        
        response = PopularDatasetsResponse(
            datasets=summaries,
            total=len(summaries)
        )

        # Cache result
        try:
            await cache.set(CACHE_KEY_POPULAR_DATASETS, response.model_dump_json(), ex=CACHE_TTL_SECONDS)
        except Exception as e:
            logger.warning(f"Failed to cache popular datasets: {e}")

        return response

import asyncio
from typing import List, Optional, Tuple, Dict
from app.services.text_search_service import TextSearchService
from app.services.vector_search_service import VectorSearchService
from app.schemas.filters import SearchFilters
from app.utils.rrf import reciprocal_rank_fusion, FusionResult
from app.models.file_metadata import FileMetadata
from app.core.config import get_settings

settings = get_settings()


class HybridSearchService:
    def __init__(
        self, text_service: TextSearchService, vector_service: VectorSearchService
    ):
        self.text_service = text_service
        self.vector_service = vector_service

    async def search_hybrid(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 20,
        offset: int = 0,
        rrf_k: int = 60,
        keyword_weight: float = 0.5,
        vector_weight: float = 0.5,
    ) -> Tuple[List[FusionResult], int, Dict[str, FileMetadata]]:
        """
        Executes text search and vector search in parallel, merging and ranking results via Reciprocal Rank Fusion (RRF).
        """
        candidate_pool_size = (
            10000  # Fixed candidate window keeps pagination ranking stable.
        )

        # Run text search and vector search concurrently
        text_task = asyncio.create_task(
            self.text_service.search(
                query=query, filters=filters, limit=candidate_pool_size, offset=0
            )
        )
        vector_task = asyncio.create_task(
            self.vector_service.search_by_query(
                query=query, filters=filters, limit=candidate_pool_size, offset=0
            )
        )

        (
            (text_ranked, text_total, files_map),
            (vector_ranked, vector_total),
        ) = await asyncio.gather(text_task, vector_task)

        # Merge via Reciprocal Rank Fusion
        fused_items = reciprocal_rank_fusion(
            keyword_results=text_ranked,
            vector_results=vector_ranked,
            k=rrf_k or settings.RRF_K,
            keyword_weight=keyword_weight,
            vector_weight=vector_weight,
        )

        total_unique_matches = min(max(text_total, vector_total), candidate_pool_size)
        paginated_results = fused_items[offset : offset + limit]

        return paginated_results, total_unique_matches, files_map

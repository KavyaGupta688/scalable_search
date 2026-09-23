import asyncio
from typing import List, Optional, Tuple, Dict
from app.services.text_search_service import TextSearchService
from app.services.vector_search_service import VectorSearchService
from app.schemas.filters import SearchFilters
from app.utils.rrf import reciprocal_rank_fusion, FusionResult
from app.models.file_metadata import FileMetadata
from app.core.config import get_settings

settings = get_settings()

# Keyword matches are already limited to documents that contain a query term.
KEYWORD_CANDIDATES = 10000


class HybridSearchService:
    def __init__(
        self, text_service: TextSearchService, vector_service: VectorSearchService
    ):
        self.text_service = text_service
        self.vector_service = vector_service

    async def fuse_candidates(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        rrf_k: int = 60,
        keyword_weight: float = 0.5,
        vector_weight: float = 0.5,
    ) -> Tuple[List[FusionResult], Dict[str, FileMetadata]]:
        """
        Runs keyword and vector retrieval concurrently and fuses ALL candidates with
        Reciprocal Rank Fusion. Pagination is left to the caller so that ranking
        adjustments apply to the whole candidate set, not to a single page.

        Both branches apply the same filters. The vector branch only contributes hits
        within the configured similarity margin of its best hit.
        """
        text_task = asyncio.create_task(
            self.text_service.search(
                query=query, filters=filters, limit=KEYWORD_CANDIDATES, offset=0
            )
        )
        vector_task = asyncio.create_task(
            self.vector_service.search_by_query(
                query=query, filters=filters, limit=settings.VECTOR_CANDIDATES, offset=0
            )
        )

        (
            (text_ranked, _text_total, files_map),
            (vector_ranked, _vector_total),
        ) = await asyncio.gather(text_task, vector_task)

        fused = reciprocal_rank_fusion(
            keyword_results=text_ranked,
            vector_results=vector_ranked,
            k=rrf_k or settings.RRF_K,
            keyword_weight=keyword_weight,
            vector_weight=vector_weight,
        )
        return fused, files_map

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
        """One page of fused results. total is the number of fused candidates."""
        fused, files_map = await self.fuse_candidates(
            query, filters, rrf_k, keyword_weight, vector_weight
        )
        return fused[offset : offset + limit], len(fused), files_map

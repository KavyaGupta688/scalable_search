import asyncio
from typing import List, Optional, Tuple, Dict
from app.services.text_search_service import TextSearchService
from app.services.vector_search_service import VectorSearchService
from app.schemas.filters import SearchFilters
from app.utils.rrf import reciprocal_rank_fusion, FusionResult
from app.models.file_metadata import FileMetadata
from app.core.config import get_settings

settings = get_settings()

# Bound neural work per query. Exact Keyword mode remains available for exhaustive matching.
KEYWORD_CANDIDATES = settings.VECTOR_CANDIDATES


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
        after local query/document relevance verification.
        """
        from app.utils.query_normalizer import search_intent, tokenize
        original_query = query
        query, _ = search_intent(query)
        if not tokenize(query):
            return [], {}
        async def keyword_branch():
            if keyword_weight == 0:
                return [], 0, {}
            return await self.text_service.search(
                query=query, filters=filters, limit=KEYWORD_CANDIDATES, offset=0,
                match_all=False,
            )
        async def vector_branch():
            if vector_weight == 0:
                return [], 0
            return await self.vector_service.search_by_query(
                query=query, filters=filters, limit=settings.VECTOR_CANDIDATES, offset=0,
            )
        (text_ranked, _text_total, files_map), (vector_ranked, _vector_total) = await asyncio.gather(
            keyword_branch(), vector_branch()
        )

        fused = reciprocal_rank_fusion(
            keyword_results=text_ranked,
            vector_results=vector_ranked,
            k=rrf_k or settings.RRF_K,
            keyword_weight=keyword_weight,
            vector_weight=vector_weight,
        )
        missing = [item.id for item in fused if item.id not in files_map]
        if missing:
            for file in await self.text_service.file_repo.get_by_ids(missing):
                files_map[file.file_id] = file
        from starlette.concurrency import run_in_threadpool
        from app.services.relevance_service import rerank
        fused = await run_in_threadpool(rerank, original_query, fused, files_map)
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

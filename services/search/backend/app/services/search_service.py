import time
import logging
from typing import Optional, List
from app.services.query_processor import QueryProcessor
from app.services.hybrid_search_service import HybridSearchService
from app.services.text_search_service import TextSearchService
from app.services.vector_search_service import VectorSearchService
from app.services.ranking_service import RankingService
from app.services.metadata_service import MetadataService
from app.services.facet_service import FacetService
from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.search import (
    SearchRequest,
    SearchResponse,
    VectorSearchRequest,
    SimilarSearchRequest
)
from app.schemas.filters import SearchFilters
from app.utils.rrf import RankedItem, FusionResult
from app.utils.query_normalizer import normalize_query_for_trending

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(
        self,
        query_processor: QueryProcessor,
        hybrid_service: HybridSearchService,
        text_service: TextSearchService,
        vector_service: VectorSearchService,
        ranking_service: RankingService,
        metadata_service: MetadataService,
        facet_service: FacetService,
        analytics_repo: AnalyticsRepository
    ):
        self.query_processor = query_processor
        self.hybrid_service = hybrid_service
        self.text_service = text_service
        self.vector_service = vector_service
        self.ranking_service = ranking_service
        self.metadata_service = metadata_service
        self.facet_service = facet_service
        self.analytics_repo = analytics_repo

    async def execute_search(
        self,
        req: SearchRequest,
        user_id: str = "usr_guest_demo",
        user_role: str = "ANALYST"
    ) -> SearchResponse:
        start_time = time.perf_counter()
        
        # 1. Query Processing & Normalization
        processed = self.query_processor.process_query(req.query, req.filters)
        active_filters = req.filters or processed.get("filters")
        
        # 2. Mode Routing (Hybrid RRF / Vector / Text)
        mode = req.search_mode.lower()
        
        if mode == "vector":
            ranked_vec, total_hits = await self.vector_service.search_by_query(
                query=req.query,
                filters=active_filters,
                limit=req.limit,
                offset=req.offset
            )
            fused_results = [
                FusionResult(
                    id=r.id,
                    rrf_score=r.raw_score,
                    vector_rank=r.rank,
                    vector_similarity=r.raw_score,
                    match_sources=["vector"]
                ) for r in ranked_vec
            ]
            files_map = {}
            total = total_hits
            
        elif mode == "text":
            ranked_txt, total_hits, files_map = await self.text_service.search(
                query=req.query,
                filters=active_filters,
                limit=req.limit,
                offset=req.offset
            )
            fused_results = [
                FusionResult(
                    id=r.id,
                    rrf_score=r.raw_score,
                    keyword_rank=r.rank,
                    text_score=r.raw_score,
                    match_sources=["keyword"]
                ) for r in ranked_txt
            ]
            total = total_hits
            
        else:
            # Default: Hybrid Search (RRF)
            fused_results, total, files_map = await self.hybrid_service.search_hybrid(
                query=req.query,
                filters=active_filters,
                limit=req.limit,
                offset=req.offset,
                rrf_k=req.rrf_k or 60,
                keyword_weight=req.keyword_weight or 0.5,
                vector_weight=req.vector_weight or 0.5
            )

        # 3. Ranking and Score Fine-tuning
        ranked_results = self.ranking_service.rank_and_adjust(fused_results, files_map)

        # 4. Metadata Hydration
        hydrated_results = await self.metadata_service.hydrate_results(ranked_results, files_map)

        # 5. Facet Computation
        facets = await self.facet_service.get_facets(query=req.query, filters=active_filters)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        # 6. Asynchronously record search event
        try:
            norm_q = normalize_query_for_trending(req.query)
            await self.analytics_repo.log_event(
                event_type="SEARCH",
                user_id=user_id,
                user_role=user_role,
                query=req.query,
                normalized_query=norm_q,
                filters=active_filters.model_dump(exclude_none=True) if active_filters else None,
                result_count=total
            )
        except Exception as e:
            logger.warning(f"Failed to log search event: {e}")

        return SearchResponse(
            query=req.query,
            search_mode=mode,
            total=total,
            limit=req.limit,
            offset=req.offset,
            execution_time_ms=round(elapsed_ms, 2),
            results=hydrated_results,
            facets=facets
        )

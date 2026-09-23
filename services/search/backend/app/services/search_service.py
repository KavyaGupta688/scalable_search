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
    SimilarSearchRequest,
)
from app.schemas.filters import SearchFilters
from app.utils.download_plan import build_plan
from modules.shared import download_limits
from app.utils.rrf import RankedItem, FusionResult
from app.utils.query_normalizer import normalize_query_for_trending
from app.core.config import get_settings
from app.repositories.file_repository import SELF_IGNORING_FACETS

logger = logging.getLogger(__name__)
settings = get_settings()


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
        analytics_repo: AnalyticsRepository,
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
        user_role: str = "ANALYST",
    ) -> SearchResponse:
        start_time = time.perf_counter()

        # 1. Query Processing & Normalization
        processed = self.query_processor.process_query(req.query, req.filters)
        active_filters = req.filters or processed.get("filters")

        # 2. Mode Routing (Hybrid RRF / Vector / Text)
        mode = req.search_mode.lower()
        # Ids of every document this search matched. Hybrid and vector matches cannot be
        # derived from the keyword query, so their facets are counted over exactly this
        # set. None means the keyword query itself defines the matches (text mode).
        scope_ids = None

        if mode == "vector":
            relevant, total = await self.vector_service.search_by_query(
                query=req.query,
                filters=active_filters,
                limit=settings.VECTOR_CANDIDATES,
                offset=0,
            )
            scope_ids = [r.id for r in relevant]
            fused_results = [
                FusionResult(
                    id=r.id,
                    rrf_score=r.raw_score,
                    vector_rank=r.rank,
                    vector_similarity=r.raw_score,
                    match_sources=["vector"],
                )
                for r in relevant[req.offset : req.offset + req.limit]
            ]
            files_map = {}

        elif mode == "text":
            ranked_txt, total_hits, files_map = await self.text_service.search(
                query=req.query,
                filters=active_filters,
                limit=req.limit,
                offset=req.offset,
            )
            fused_results = [
                FusionResult(
                    id=r.id,
                    rrf_score=r.raw_score,
                    keyword_rank=r.rank,
                    text_score=r.raw_score,
                    match_sources=["keyword"],
                )
                for r in ranked_txt
            ]
            total = total_hits

        else:
            # Default: Hybrid Search (RRF). Fuse every candidate, adjust the whole set,
            # then paginate, so boosts cannot reorder results across page boundaries.
            fused_all, files_map = await self.hybrid_service.fuse_candidates(
                query=req.query,
                filters=active_filters,
                rrf_k=req.rrf_k or 60,
                keyword_weight=req.keyword_weight or 0.5,
                vector_weight=req.vector_weight or 0.5,
            )
            await self._attach_files(fused_all, files_map)
            ranked_all = self.ranking_service.rank_and_adjust(
                [r for r in fused_all if r.id in files_map], files_map
            )
            total = len(ranked_all)
            scope_ids = [r.id for r in ranked_all]
            fused_results = ranked_all[req.offset : req.offset + req.limit]

        # 3. Metadata Hydration
        hydrated_results = await self.metadata_service.hydrate_results(
            fused_results, files_map
        )

        # 4. Facet Computation
        relaxed_ids = {}
        if scope_ids is not None and active_filters:
            # Each facet ignores its own filter, so it needs the same search without it.
            for facet, fields in SELF_IGNORING_FACETS.items():
                if any(getattr(active_filters, f) is not None for f in fields):
                    relaxed_ids[facet] = await self._candidate_ids(
                        req, mode, active_filters, fields
                    )
        facets = await self.facet_service.get_facets(
            query=req.query,
            filters=active_filters,
            scope_ids=scope_ids,
            relaxed_scope_ids=relaxed_ids,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        # 6. Asynchronously record search event
        norm_q = normalize_query_for_trending(req.query)
        await self.analytics_repo.log_event(
            event_type="SEARCH",
            user_id=user_id,
            user_role=user_role,
            query=req.query,
            normalized_query=norm_q,
            filters=active_filters.model_dump(exclude_none=True)
            if active_filters
            else None,
            result_count=total,
            execution_time_ms=max(1, round(elapsed_ms)),
        )

        return SearchResponse(
            query=req.query,
            search_mode=mode,
            total=total,
            limit=req.limit,
            offset=req.offset,
            execution_time_ms=round(elapsed_ms, 2),
            results=hydrated_results,
            facets=facets,
        )

    async def download_plan(self, req):
        """Which files a download of the top N results would contain, and how big it is.

        Ordering is the search's own, so the files are the N at the top of the results list.
        """
        processed = self.query_processor.process_query(req.query, req.filters)
        filters = req.filters or processed.get("filters")
        mode = req.search_mode.lower()
        repo = self.metadata_service.file_repo
        scan = settings.DOWNLOAD_PLAN_SCAN

        if mode == "text":
            ranked, total = await repo.ranked_sizes(req.query, filters, scan)
        elif mode == "vector":
            relevant, total = await self.vector_service.search_by_query(
                query=req.query, filters=filters, limit=settings.VECTOR_CANDIDATES, offset=0
            )
            sizes = await repo.sizes_for([r.id for r in relevant])
            ranked = [(r.id, sizes[r.id]) for r in relevant if r.id in sizes]
        else:
            fused, files_map = await self.hybrid_service.fuse_candidates(
                query=req.query,
                filters=filters,
                rrf_k=req.rrf_k or 60,
                keyword_weight=req.keyword_weight or 0.5,
                vector_weight=req.vector_weight or 0.5,
            )
            await self._attach_files(fused, files_map)
            ordered = self.ranking_service.rank_and_adjust(
                [r for r in fused if r.id in files_map], files_map
            )
            total = len(ordered)
            ranked = [(r.id, int(files_map[r.id].file_size)) for r in ordered][:scan]

        return build_plan(
            ranked,
            total_matches=total,
            count=req.count,
            limits=download_limits.limits(),
            include_ids=req.include_ids,
        )

    async def _attach_files(self, fused, files_map):
        """Loads metadata for candidates the keyword branch did not return."""
        missing = [r.id for r in fused if r.id not in files_map]
        if missing:
            for file in await self.metadata_service.file_repo.get_by_ids(missing):
                files_map[file.file_id] = file

    async def _candidate_ids(self, req, mode, filters, ignore):
        """Ids matched by this search with the given filter fields ignored."""
        relaxed = filters.model_copy(update={field: None for field in ignore})
        if mode == "vector":
            relevant, _ = await self.vector_service.search_by_query(
                query=req.query, filters=relaxed, limit=settings.VECTOR_CANDIDATES, offset=0
            )
            return [r.id for r in relevant]
        fused, _ = await self.hybrid_service.fuse_candidates(
            query=req.query,
            filters=relaxed,
            rrf_k=req.rrf_k or 60,
            keyword_weight=req.keyword_weight or 0.5,
            vector_weight=req.vector_weight or 0.5,
        )
        return [r.id for r in fused]

import asyncio
import logging
import time
from typing import List, Optional, Tuple, Dict
from app.services.text_search_service import TextSearchService
from app.services.vector_search_service import VectorSearchService
from app.schemas.filters import SearchFilters
from app.utils.rrf import reciprocal_rank_fusion, FusionResult
from app.models.file_metadata import FileMetadata
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Bound neural work per query. Exact Keyword mode remains available for exhaustive matching.
KEYWORD_CANDIDATES = settings.VECTOR_CANDIDATES


class CircuitBreaker:
    """Skip a failing dependency for a cool-down instead of waiting on it every request."""

    def __init__(self, threshold, cooldown):
        self.threshold, self.cooldown = threshold, cooldown
        self.failures, self.open_until = 0, 0.0

    def allow(self):
        return time.monotonic() >= self.open_until

    def success(self):
        self.failures = 0

    def failure(self):
        self.failures += 1
        if self.failures >= self.threshold:
            self.open_until = time.monotonic() + self.cooldown
            self.failures = 0


VECTOR_BREAKER = CircuitBreaker(
    settings.VECTOR_BREAKER_THRESHOLD, settings.VECTOR_BREAKER_COOLDOWN_SECONDS
)


def lexical_fallback(query, items, files):
    """Strict stand-in for the relevance verifier when it is unavailable.

    Keeps only documents containing every query term (the text-mode rule) and honours
    explicit exclusions, so an answer without the verifier is narrower, never looser.
    """
    from app.services.relevance_service import _matches, _terms, excluded_match
    from app.utils.query_normalizer import search_intent

    positive, excluded = search_intent(query)
    terms = _terms(positive)
    fields = ("title", "description", "caption", "file_name", "content_summary",
              "ocr_text", "transcript", "category")
    kept = []
    for item in items:
        file = files.get(item.id)
        if file is None or (excluded and excluded_match(excluded, file)):
            continue
        text = " ".join(str(getattr(file, f, "") or "") for f in fields)
        text += " " + " ".join(str(tag) for tag in (getattr(file, "tags", None) or []))
        if terms and all(_matches(term, text) for term in terms):
            kept.append(item)
    return kept


class HybridSearchService:
    def __init__(
        self, text_service: TextSearchService, vector_service: VectorSearchService
    ):
        self.text_service = text_service
        self.vector_service = vector_service
        # Components this request had to answer without (reported in SearchResponse).
        self.degraded_components: List[str] = []

    def _degrade(self, component):
        from app.core.metrics import DEGRADED

        if component not in self.degraded_components:
            self.degraded_components.append(component)
            DEGRADED.labels(component=component).inc()

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
        after local query/document relevance verification. If the vector branch fails,
        the keyword branch alone answers and the component is listed as degraded.
        """
        from app.utils.query_normalizer import search_intent, tokenize
        from app.services import search_cache
        original_query = query
        query, _ = search_intent(query)
        if not tokenize(query):
            return [], {}
        cache_parts = [original_query, filters.model_dump(mode="json") if filters else None,
                       rrf_k, keyword_weight, vector_weight]
        hit, cached = await search_cache.get("hybrid", cache_parts)
        if hit:
            # Only the ranking is cached. Rows are reloaded through the SQL visibility
            # gate, which drops anything revoked since the entry was written.
            fused = [FusionResult(**item) for item in cached]
            files_map = {
                file.file_id: file
                for file in await self.text_service.file_repo.get_by_ids([r.id for r in fused])
            }
            return [r for r in fused if r.id in files_map], files_map

        computed_at = time.time()

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
            if not VECTOR_BREAKER.allow():
                raise RuntimeError("Vector search circuit is open")
            try:
                result = await asyncio.wait_for(
                    self.vector_service.search_by_query(
                        query=query, filters=filters, limit=settings.VECTOR_CANDIDATES, offset=0,
                    ),
                    settings.VECTOR_TIMEOUT_SECONDS,
                )
            except Exception:
                VECTOR_BREAKER.failure()
                raise
            VECTOR_BREAKER.success()
            return result
        (text_ranked, _text_total, files_map), vector_outcome = await self._gather(
            keyword_branch(), vector_branch()
        )
        if isinstance(vector_outcome, BaseException):
            if keyword_weight == 0:
                # Nothing else can answer a vector-only fusion.
                from fastapi import HTTPException
                raise HTTPException(503, "Vector search is unavailable") from vector_outcome
            logger.warning("Vector branch unavailable, answering from keywords: %s", vector_outcome)
            self._degrade("vector")
            vector_ranked = []
        else:
            vector_ranked, _vector_total = vector_outcome

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
        try:
            fused = await run_in_threadpool(rerank, original_query, fused, files_map)
        except Exception as exc:
            logger.warning("Relevance verifier unavailable, using strict term matching: %s", exc)
            self._degrade("rerank")
            fused = lexical_fallback(original_query, fused, files_map)
        if not self.degraded_components:
            # A partial answer is never cached, so recovery shows on the next request.
            await search_cache.put("hybrid", cache_parts, [r.model_dump() for r in fused],
                                   since=computed_at)
        return fused, files_map

    @staticmethod
    async def _gather(keyword, vector):
        """Run both branches; keyword errors propagate, vector errors are returned."""
        vector_task = asyncio.ensure_future(vector)
        try:
            keyword_result = await keyword
        except BaseException:
            vector_task.cancel()
            raise
        try:
            vector_result = await vector_task
        except Exception as exc:
            vector_result = exc
        return keyword_result, vector_result

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

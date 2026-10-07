from typing import Dict, Optional, Sequence
from app.repositories.file_repository import FileRepository
from app.schemas.filters import SearchFilters, FacetsResponse

class FacetService:
    def __init__(self, file_repo: FileRepository):
        self.file_repo = file_repo

    async def get_facets(
        self,
        query: str = "",
        filters: Optional[SearchFilters] = None,
        scope_ids: Optional[Sequence[str]] = None,
        relaxed_scope_ids: Optional[Dict[str, Sequence[str]]] = None,
    ) -> FacetsResponse:
        """
        Computes faceted metadata aggregation for the current search context, or for
        the exact result set of a hybrid/vector search when scope_ids is given.
        """
        import time
        from app.core.metrics import STAGE_LATENCY
        from app.services import search_cache

        parts = [
            query,
            filters.model_dump(mode="json") if filters else None,
            sorted(scope_ids) if scope_ids is not None else None,
            {k: sorted(v) for k, v in (relaxed_scope_ids or {}).items() if v is not None},
        ]
        hit, cached = await search_cache.get("facets", parts)
        if hit:
            return FacetsResponse.model_validate(cached)
        started, computed_at = time.perf_counter(), time.time()
        facets = await self.file_repo.compute_facets(
            query=query,
            filters=filters,
            scope_ids=scope_ids,
            relaxed_scope_ids=relaxed_scope_ids,
        )
        STAGE_LATENCY.labels(stage="facets").observe(time.perf_counter() - started)
        await search_cache.put("facets", parts, facets.model_dump(mode="json"), since=computed_at)
        return facets

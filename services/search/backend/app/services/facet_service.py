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
        return await self.file_repo.compute_facets(
            query=query,
            filters=filters,
            scope_ids=scope_ids,
            relaxed_scope_ids=relaxed_scope_ids,
        )

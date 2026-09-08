from typing import Optional
from app.repositories.file_repository import FileRepository
from app.schemas.filters import SearchFilters, FacetsResponse

class FacetService:
    def __init__(self, file_repo: FileRepository):
        self.file_repo = file_repo

    async def get_facets(self, query: str = "", filters: Optional[SearchFilters] = None) -> FacetsResponse:
        """
        Computes faceted metadata aggregation for the current search context.
        """
        return await self.file_repo.compute_facets(query=query, filters=filters)

from datetime import UTC, datetime

from modules.searching.domain.models import SearchRequest, SearchResponse, SearchResult


class SearchService:
    def __init__(self) -> None:
        self._files = [
            SearchResult(
                file_id="file-001", name="product-launch.jpg", content_type="image",
                description="Product launch event photography", tags=["launch", "product", "event"],
                score=0.98, created_at=datetime(2026, 1, 15, tzinfo=UTC),
            ),
            SearchResult(
                file_id="file-002", name="quarterly-report.pdf", content_type="document",
                description="Quarterly business performance report", tags=["finance", "quarterly", "report"],
                score=0.91, created_at=datetime(2026, 2, 1, tzinfo=UTC),
            ),
        ]

    def search(self, request: SearchRequest) -> SearchResponse:
        query = request.query.casefold()
        results = [
            item for item in self._files
            if (request.content_type is None or item.content_type == request.content_type)
            and (query in item.name.casefold() or query in item.description.casefold()
                 or any(query in tag.casefold() for tag in item.tags))
        ][: request.limit]
        return SearchResponse(query=request.query, mode=request.mode, total=len(results), results=results)
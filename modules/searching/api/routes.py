from fastapi import APIRouter

from modules.searching.application.service import SearchService
from modules.searching.domain.models import SearchRequest, SearchResponse

router = APIRouter()
service = SearchService()


@router.post("", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    return service.search(request)


@router.get("/facets")
def facets() -> dict[str, list[str]]:
    return {"content_type": ["image", "document", "video", "audio"]}
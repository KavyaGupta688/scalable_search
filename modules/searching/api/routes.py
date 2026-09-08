from fastapi import APIRouter, Depends

from modules.searching.application.service import SearchService
from modules.searching.domain.models import SearchRequest, SearchResponse
from modules.shared.audit import record
from modules.shared.auth import current_user

router = APIRouter()
service = SearchService()


@router.post("", response_model=SearchResponse)
def search(request: SearchRequest, user: dict[str, str] = Depends(current_user)) -> SearchResponse:
    response = service.search(request)
    record("search", user["sub"], "query", request.query, query=request.query,
           metadata={"mode": request.mode, "result_count": response.total})
    return response


@router.get("/facets")
def facets() -> dict[str, list[str]]:
    return {"content_type": ["image", "document", "video", "audio"]}

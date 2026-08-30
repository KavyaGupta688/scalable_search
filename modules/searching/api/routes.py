from fastapi import APIRouter, Depends

from modules.searching.application.service import SearchService
from modules.searching.domain.models import SearchRequest, SearchResponse
from modules.shared.auth.dependencies import get_current_user
from modules.shared.auth.models import UserInDB

router = APIRouter()
service = SearchService()


@router.post("", response_model=SearchResponse)
def search(
    request: SearchRequest,
    _user: UserInDB = Depends(get_current_user),
) -> SearchResponse:
    return service.search(request)


@router.get("/facets")
def facets(
    _user: UserInDB = Depends(get_current_user),
) -> dict[str, list[str]]:
    return {"content_type": ["image", "document", "video", "audio"]}
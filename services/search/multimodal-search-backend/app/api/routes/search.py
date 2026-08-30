from fastapi import APIRouter, Depends, status
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search_service import SearchService
from app.core.dependencies import get_search_service
from app.core.security import get_current_user_context, UserContext

router = APIRouter()

@router.post("", response_model=SearchResponse, summary="Main hybrid search (RRF)")
async def search_files(
    request: SearchRequest,
    search_service: SearchService = Depends(get_search_service),
    user: UserContext = Depends(get_current_user_context)
):
    """
    Main multimodal search endpoint.
    Performs keyword and semantic vector search in parallel, merges and ranks results via Reciprocal Rank Fusion (RRF).
    """
    return await search_service.execute_search(
        req=request,
        user_id=user.user_id,
        user_role=user.role
    )

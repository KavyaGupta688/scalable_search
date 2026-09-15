from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from app.schemas.search import SearchRequest, SearchResponse
from app.schemas.filters import SearchFilters
from app.services.search_service import SearchService
from app.core.dependencies import get_search_service
from app.core.security import get_current_user_context, UserContext

router = APIRouter()

@router.get("", response_model=SearchResponse, summary="Keyword and metadata full-text search")
async def search_text(
    q: str = Query(..., description="Keyword query"),
    file_type: Optional[List[str]] = Query(None),
    category: Optional[List[str]] = Query(None),
    dataset_id: Optional[List[str]] = Query(None),
    ai_generated: Optional[bool] = Query(None),
    pii_detected: Optional[bool] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search_service: SearchService = Depends(get_search_service),
    user: UserContext = Depends(get_current_user_context)
):
    """
    Performs keyword and metadata search against full-text indexed file records.
    """
    filters = SearchFilters(
        file_types=file_type,
        categories=category,
        dataset_ids=dataset_id,
        ai_generated=ai_generated,
        pii_detected=pii_detected
    )
    req = SearchRequest(
        query=q,
        filters=filters,
        search_mode="text",
        limit=limit,
        offset=offset
    )
    return await search_service.execute_search(
        req=req,
        user_id=user.user_id,
        user_role=user.role
    )

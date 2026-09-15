from fastapi import APIRouter, Depends, Query
from app.schemas.search import SuggestionsResponse
from app.services.trending_service import TrendingService
from app.core.dependencies import get_trending_service

router = APIRouter()

@router.get("", response_model=SuggestionsResponse, summary="Autocomplete search suggestions")
async def get_search_suggestions(
    q: str = Query(..., min_length=1, description="Query prefix to autocomplete"),
    limit: int = Query(8, ge=1, le=20),
    trending_service: TrendingService = Depends(get_trending_service)
):
    """
    Returns autocomplete suggestions matching query prefix across trending searches, datasets, categories, and AI tags.
    """
    return await trending_service.get_suggestions(query=q, limit=limit)

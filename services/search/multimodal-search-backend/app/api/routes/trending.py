from fastapi import APIRouter, Depends, Query
from app.schemas.search import TrendingResponse
from app.services.trending_service import TrendingService
from app.core.dependencies import get_trending_service

router = APIRouter()

@router.get("", response_model=TrendingResponse, summary="Get trending search queries")
async def get_trending_searches(
    limit: int = Query(8, ge=1, le=20, description="Max trending searches to return"),
    trending_service: TrendingService = Depends(get_trending_service)
):
    """
    Returns recently popular search queries aggregated from normalized user search events over the last 24 hours.
    """
    return await trending_service.get_trending(limit=limit)

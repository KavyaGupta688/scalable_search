from fastapi import APIRouter, Depends, Query
from app.schemas.dataset import PopularDatasetsResponse
from app.services.popular_dataset_service import PopularDatasetService
from app.core.dependencies import get_popular_dataset_service

router = APIRouter()

@router.get("/popular", response_model=PopularDatasetsResponse, summary="Get dynamically ranked popular datasets")
async def get_popular_datasets(
    limit: int = Query(8, ge=1, le=20, description="Max datasets to return"),
    popular_service: PopularDatasetService = Depends(get_popular_dataset_service)
):
    """
    Returns datasets ranked by cumulative popularity score (recorded views and downloads).
    Each item also carries view_count_7d, the dataset opens recorded in the last 7 days.
    """
    return await popular_service.get_popular_datasets(limit=limit)

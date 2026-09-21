from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from app.schemas.filters import SearchFilters, FacetsResponse
from app.services.facet_service import FacetService
from app.core.dependencies import get_facet_service

router = APIRouter()

@router.get("", response_model=FacetsResponse, summary="Get dynamic search facets and counts")
async def get_facets(
    q: Optional[str] = Query("", description="Current search query context"),
    file_type: Optional[List[str]] = Query(None),
    category: Optional[List[str]] = Query(None),
    dataset_id: Optional[List[str]] = Query(None),
    ai_generated: Optional[bool] = Query(None),
    pii_detected: Optional[bool] = Query(None),
    resolution: Optional[List[str]] = Query(None, description="4k, 2k, fhd, hd, sd, unknown"),
    size: Optional[List[str]] = Query(None, description="lt100k, 100k-1m, 1m-10m, 10m-100m, 100m-1g, gte1g"),
    min_size: Optional[int] = Query(None, ge=0),
    max_size: Optional[int] = Query(None, ge=0),
    facet_service: FacetService = Depends(get_facet_service)
):
    """
    Returns available filter buckets (file types, categories, datasets, AI flag, PII, top tags) with matching counts.
    """
    filters = SearchFilters(
        file_types=file_type,
        categories=category,
        dataset_ids=dataset_id,
        ai_generated=ai_generated,
        pii_detected=pii_detected,
        resolutions=resolution,
        size_buckets=size,
        min_size=min_size,
        max_size=max_size,
    )
    return await facet_service.get_facets(query=q or "", filters=filters)

from fastapi import APIRouter, Depends
from app.schemas.search import SimilarSearchRequest, SearchResponse, SearchResultItem
from app.services.similar_search_service import SimilarSearchService
from app.services.metadata_service import MetadataService
from app.core.dependencies import get_similar_search_service, get_metadata_service
from app.core.security import get_current_user_context, UserContext
from app.utils.rrf import FusionResult
import time

router = APIRouter()

@router.post("", response_model=SearchResponse, summary="Find similar files to an existing file")
async def find_similar_files(
    request: SimilarSearchRequest,
    similar_service: SimilarSearchService = Depends(get_similar_search_service),
    metadata_service: MetadataService = Depends(get_metadata_service),
    user: UserContext = Depends(get_current_user_context)
):
    """
    Retrieves vector of the target file_id, executes cosine similarity search excluding the original, and returns similar files.
    """
    start_time = time.perf_counter()
    
    ranked_items, total = await similar_service.find_similar(
        file_id=request.file_id,
        filters=request.filters,
        limit=request.limit
    )

    fused_results = [
        FusionResult(
            id=r.id,
            rrf_score=r.raw_score,
            vector_rank=r.rank,
            vector_similarity=r.raw_score,
            match_sources=["similarity_vector"]
        ) for r in ranked_items
    ]

    hydrated = await metadata_service.hydrate_results(fused_results)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    return SearchResponse(
        query=f"similar_to:{request.file_id}",
        search_mode="similar",
        total=total,
        limit=request.limit,
        offset=0,
        execution_time_ms=round(elapsed_ms, 2),
        results=hydrated,
        facets=None
    )

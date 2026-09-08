from fastapi import APIRouter, Depends
from app.schemas.search import VectorSearchRequest, SearchRequest, SearchResponse
from app.services.search_service import SearchService
from app.core.dependencies import get_search_service
from app.core.security import get_current_user_context, UserContext

router = APIRouter()

@router.post("", response_model=SearchResponse, summary="Semantic vector search")
async def search_vector(
    request: VectorSearchRequest,
    search_service: SearchService = Depends(get_search_service),
    user: UserContext = Depends(get_current_user_context)
):
    """
    Converts a natural-language query into an embedding vector and searches Qdrant vector database.
    """
    search_req = SearchRequest(
        query=request.query,
        filters=request.filters,
        search_mode="vector",
        limit=request.limit,
        offset=request.offset
    )
    return await search_service.execute_search(
        req=search_req,
        user_id=user.user_id,
        user_role=user.role
    )

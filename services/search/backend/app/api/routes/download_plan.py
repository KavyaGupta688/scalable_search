from fastapi import APIRouter, Depends

from app.core.dependencies import get_search_service
from app.core.security import UserContext, get_current_user_context
from app.schemas.search import DownloadPlanRequest, DownloadPlanResponse
from app.services.search_service import SearchService

router = APIRouter()


@router.post(
    "",
    response_model=DownloadPlanResponse,
    response_model_exclude_none=True,
    summary="Plan a download of the top N search results",
)
async def plan_download(
    request: DownloadPlanRequest,
    search_service: SearchService = Depends(get_search_service),
    user: UserContext = Depends(get_current_user_context),
):
    """
    Returns how many files a download of the top N results contains, their total size, how many
    archive parts that needs, and whether it fits the download limits. With include_ids it also
    returns the file ids to hand to POST /downloads/batch.
    """
    return await search_service.download_plan(request)

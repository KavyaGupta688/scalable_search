from fastapi import APIRouter, Depends, status
from app.schemas.events import (
    SearchEventCreate,
    SearchEventResponse,
    DownloadExportRequest,
    DownloadExportResponse
)
from app.services.event_service import EventService
from app.core.dependencies import get_event_service
from app.core.security import get_current_user_context, UserContext

router = APIRouter()

@router.post("/search", response_model=SearchEventResponse, status_code=status.HTTP_201_CREATED, summary="Record search, preview or click event")
async def record_event(
    event: SearchEventCreate,
    event_service: EventService = Depends(get_event_service),
    user: UserContext = Depends(get_current_user_context)
):
    """
    Records search, preview, similarity, or dataset open events for audit trails and analytics.
    """
    return await event_service.record_search_event(
        event_data=event,
        user_id=user.user_id,
        user_role=user.role
    )

@router.post("/export-download", response_model=DownloadExportResponse, summary="Send selected files to Download & Auditing module")
async def export_for_download(
    request: DownloadExportRequest,
    event_service: EventService = Depends(get_event_service),
    user: UserContext = Depends(get_current_user_context)
):
    """
    Batches selected file IDs, bundles metadata.csv, logs tamper-evident audit event, and dispatches to Download & Auditing module.
    """
    return await event_service.handle_download_export(
        request=request,
        user_id=user.user_id,
        user_role=user.role
    )

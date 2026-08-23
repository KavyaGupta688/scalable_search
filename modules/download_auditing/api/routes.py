from fastapi import APIRouter, HTTPException, Query

from modules.download_auditing.application.service import DownloadAuditingService
from modules.download_auditing.domain.models import (
    AuditAction,
    AuditEventsResponse,
    DownloadBatch,
    DownloadRequest,
)

router = APIRouter()
service = DownloadAuditingService()


@router.post("/batch", status_code=202, response_model=DownloadBatch)
def create_batch_download(request: DownloadRequest) -> DownloadBatch:
    try:
        return service.create_batch_download(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/audit/events", response_model=AuditEventsResponse)
def audit_events(
    action: AuditAction | None = None,
    actor: str | None = Query(default=None, min_length=1, max_length=120),
    download_id: str | None = Query(default=None, min_length=1, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
) -> AuditEventsResponse:
    return service.list_audit_events(action=action, actor=actor, entity_id=download_id, limit=limit)


@router.get("/{download_id}", response_model=DownloadBatch)
def download_status(
    download_id: str,
    actor: str = Query(default="auditor-demo", min_length=1, max_length=120),
) -> DownloadBatch:
    try:
        return service.get_download(download_id, actor=actor)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Download batch not found") from exc
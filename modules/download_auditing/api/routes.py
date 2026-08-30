from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from modules.download_auditing.application.service import DownloadAuditingService
from modules.download_auditing.domain.models import (
    AuditAction,
    AuditEventsResponse,
    DownloadBatch,
    DownloadRequest,
)
from modules.shared.auth import require_roles

router = APIRouter()
service = DownloadAuditingService()

class AuditEventRequest(BaseModel):
    action: str = Field(min_length=1, max_length=80)
    entity_type: str = Field(min_length=1, max_length=120)
    entity_id: str = Field(min_length=1, max_length=200)
    query: str | None = Field(default=None, max_length=500)
    device: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    metadata: dict[str, object] = Field(default_factory=dict)

@router.post("/events", status_code=201)
def create_audit_event(request: AuditEventRequest, user: dict[str, str] = Depends(require_roles("admin", "analyst"))) -> dict[str, object]:
    event = service.record_event(request.action, user["sub"], request.entity_type, request.entity_id,
                                 query=request.query, device=request.device, location=request.location,
                                 metadata=request.metadata)
    return event.model_dump(mode="json")


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
    user: dict[str, str] = Depends(require_roles("admin")),
) -> AuditEventsResponse:
    return service.list_audit_events(action=action, actor=actor, entity_id=download_id, limit=limit)


@router.get("/{download_id}", response_model=DownloadBatch)
def download_status(
    download_id: str,
    actor: str = Query(default="auditor-demo", min_length=1, max_length=120),
    user: dict[str, str] = Depends(require_roles("admin", "analyst", "viewer")),
) -> DownloadBatch:
    try:
        return service.get_download(download_id, actor=actor)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Download batch not found") from exc

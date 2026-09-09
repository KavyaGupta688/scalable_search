from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
import csv, io
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
    user_role: str | None = Field(default=None, max_length=50)
    entity_type: str = Field(min_length=1, max_length=120)
    entity_id: str = Field(min_length=1, max_length=200)
    status: str = Field(default="SUCCESS", max_length=32)
    query: str | None = Field(default=None, max_length=500)
    device: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    client_ip: str | None = Field(default=None, max_length=64)
    correlation_id: str | None = Field(default=None, max_length=80)
    execution_time_ms: int = Field(default=0, ge=0)
    metadata: dict[str, object] = Field(default_factory=dict)

@router.post("/events", status_code=201)
def create_audit_event(request: AuditEventRequest, user: dict[str, str] = Depends(require_roles("admin", "analyst"))) -> dict[str, object]:
    role = request.user_role or user.get("role", "analyst")
    event = service.record_event(
        request.action,
        user["sub"],
        request.entity_type,
        request.entity_id,
        user_role=role,
        status=request.status,
        query=request.query,
        device=request.device,
        location=request.location,
        client_ip=request.client_ip,
        correlation_id=request.correlation_id,
        execution_time_ms=request.execution_time_ms,
        metadata=request.metadata,
    )
    return event.model_dump(mode="json")

@router.get("/audit/export.csv")
def export_audit_csv(user: dict[str, str] = Depends(require_roles("admin"))) -> StreamingResponse:
    events = service.list_audit_events(limit=500).events
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow([
        "event_id", "action", "actor", "user_role", "entity_type", "entity_id",
        "status", "occurred_at", "query", "device_code", "location_code",
        "client_ip", "correlation_id", "execution_time_ms"
    ])
    for event in events:
        writer.writerow([
            event.event_id, event.action, event.actor, event.user_role or "",
            event.entity_type, event.entity_id, event.status or "SUCCESS",
            event.occurred_at.isoformat(), event.query or "",
            event.device_code or "", event.location_code or "",
            event.client_ip or "", event.correlation_id or "",
            event.execution_time_ms or 0,
        ])
    return StreamingResponse(iter([stream.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=audit-events.csv"})


@router.post("/batch", status_code=202, response_model=DownloadBatch)
def create_batch_download(request: DownloadRequest) -> DownloadBatch:
    try:
        return service.create_batch_download(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/audit/events", response_model=AuditEventsResponse)
def audit_events(
    action: str | None = None,
    actor: str | None = Query(default=None, min_length=1, max_length=120),
    entity_type: str | None = Query(default=None, min_length=1, max_length=120),
    download_id: str | None = Query(default=None, min_length=1, max_length=120),
    status: str | None = Query(default=None, min_length=1, max_length=32),
    limit: int = Query(default=50, ge=1, le=500),
    user: dict[str, str] = Depends(require_roles("admin")),
) -> AuditEventsResponse:
    return service.list_audit_events(
        action=action,
        actor=actor,
        entity_type=entity_type,
        entity_id=download_id,
        status=status,
        limit=limit,
    )



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

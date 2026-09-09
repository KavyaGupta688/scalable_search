from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class DownloadStatus(StrEnum):
    BUILDING = "building"
    READY = "ready"


class AuditAction(StrEnum):
    SEARCH = "search"
    PREVIEW = "preview"
    LOGIN = "login"
    UPLOAD = "upload"
    EDIT = "edit"
    DELETE = "delete"
    BATCH = "batch"
    JOB = "job"
    RETRY = "retry"
    BATCH_CREATED = "download.batch.created"
    BATCH_VIEWED = "download.batch.viewed"
    AUDIT_VIEWED = "download.audit.viewed"
    # Extended platform cross-cutting actions
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    SEARCH_QUERY = "search.query"
    DOCUMENT_PREVIEW = "document.preview"
    DOCUMENT_INGESTED = "ingestion.document.ingested"
    DUPLICATE_DETECTED = "ingestion.duplicate.detected"
    AI_ENRICHMENT_COMPLETED = "ai.enrichment.completed"
    WATERMARK_INJECTED = "download.watermark.injected"
    RETENTION_PURGE_EXECUTED = "retention.purge.executed"


class DownloadRequest(BaseModel):
    file_ids: list[str] = Field(min_length=1, max_length=100)
    requested_by: str = Field(default="analyst-demo", min_length=1, max_length=120)


class DownloadBatch(BaseModel):
    download_id: str
    status: DownloadStatus
    file_ids: list[str]
    file_count: int
    requested_by: str
    created_at: datetime
    updated_at: datetime


class AuditEvent(BaseModel):
    event_id: str
    action: str
    actor: str = Field(min_length=1, max_length=120)
    user_role: str | None = Field(default="analyst", max_length=50)
    entity_type: str = Field(min_length=1, max_length=120)
    entity_id: str = Field(min_length=1, max_length=200)
    status: str = Field(default="SUCCESS", max_length=32)
    occurred_at: datetime
    query: str | None = None
    device_code: str | None = None
    location_code: str | None = None
    client_ip: str | None = None
    correlation_id: str | None = None
    execution_time_ms: int = 0
    metadata: dict[str, object] = Field(default_factory=dict)


class AuditEventsResponse(BaseModel):
    events: list[AuditEvent]



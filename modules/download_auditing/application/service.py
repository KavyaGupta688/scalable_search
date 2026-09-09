from datetime import UTC, datetime

from modules.download_auditing.domain.models import (
    AuditAction,
    AuditEvent,
    AuditEventsResponse,
    DownloadBatch,
    DownloadRequest,
    DownloadStatus,
)
from modules.shared.audit import list_persisted, record


class DownloadAuditingService:
    def __init__(self) -> None:
        self._known_files = {"file-001", "file-002", "file-003", "file-004"}
        self._downloads: dict[str, DownloadBatch] = {}
        self._events: list[AuditEvent] = []

    def create_batch_download(self, request: DownloadRequest) -> DownloadBatch:
        unknown_file_ids = [file_id for file_id in request.file_ids if file_id not in self._known_files]
        if unknown_file_ids:
            invalid = ", ".join(unknown_file_ids)
            raise ValueError(f"Unknown file ids: {invalid}")

        now = datetime.now(UTC)
        download_id = f"download-{len(self._downloads) + 1:03d}"
        batch = DownloadBatch(
            download_id=download_id,
            status=DownloadStatus.READY,
            file_ids=request.file_ids,
            file_count=len(request.file_ids),
            requested_by=request.requested_by,
            created_at=now,
            updated_at=now,
        )
        self._downloads[download_id] = batch

        record(AuditAction.BATCH_CREATED, request.requested_by, "download_batch", download_id,
               metadata={"file_count": len(request.file_ids), "file_ids": request.file_ids})
        return batch

    def get_download(self, download_id: str, actor: str) -> DownloadBatch:
        batch = self._downloads.get(download_id)
        if batch is None:
            raise KeyError(download_id)

        record(AuditAction.BATCH_VIEWED, actor, "download_batch", download_id, metadata={"status": batch.status})
        return batch

    def list_audit_events(
        self,
        *,
        action: str | None = None,
        actor: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> AuditEventsResponse:
        persisted = list_persisted(
            action=action,
            actor=actor,
            entity_type=entity_type,
            entity_id=entity_id,
            status=status,
            limit=limit,
        )
        events = [AuditEvent.model_validate(event) for event in persisted]

        now = datetime.now(UTC)
        record(AuditAction.AUDIT_VIEWED, actor or "auditor-demo", "audit_log", "platform",
               metadata={"result_count": min(limit, len(events))})

        ordered = sorted(events, key=lambda event: event.occurred_at, reverse=True)
        return AuditEventsResponse(events=ordered[:limit])

    def record_event(self, action: str, actor: str, entity_type: str, entity_id: str, **kwargs: object) -> AuditEvent:
        return AuditEvent.model_validate(record(action, actor, entity_type, entity_id, **kwargs))



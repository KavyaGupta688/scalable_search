from datetime import UTC, datetime

from modules.download_auditing.domain.models import (
    AuditAction,
    AuditEvent,
    AuditEventsResponse,
    DownloadBatch,
    DownloadRequest,
    DownloadStatus,
)


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

        self._events.append(
            AuditEvent(
                event_id=f"audit-{len(self._events) + 1:04d}",
                action=AuditAction.BATCH_CREATED,
                actor=request.requested_by,
                entity_type="download_batch",
                entity_id=download_id,
                occurred_at=now,
                metadata={"file_count": len(request.file_ids), "file_ids": request.file_ids},
            )
        )
        return batch

    def get_download(self, download_id: str, actor: str) -> DownloadBatch:
        batch = self._downloads.get(download_id)
        if batch is None:
            raise KeyError(download_id)

        self._events.append(
            AuditEvent(
                event_id=f"audit-{len(self._events) + 1:04d}",
                action=AuditAction.BATCH_VIEWED,
                actor=actor,
                entity_type="download_batch",
                entity_id=download_id,
                occurred_at=datetime.now(UTC),
                metadata={"status": batch.status},
            )
        )
        return batch

    def list_audit_events(
        self,
        *,
        action: AuditAction | None = None,
        actor: str | None = None,
        entity_id: str | None = None,
        limit: int = 50,
    ) -> AuditEventsResponse:
        events = self._events
        if action is not None:
            events = [event for event in events if event.action == action]
        if actor is not None:
            events = [event for event in events if event.actor == actor]
        if entity_id is not None:
            events = [event for event in events if event.entity_id == entity_id]

        now = datetime.now(UTC)
        self._events.append(
            AuditEvent(
                event_id=f"audit-{len(self._events) + 1:04d}",
                action=AuditAction.AUDIT_VIEWED,
                actor=actor or "auditor-demo",
                entity_type="audit_log",
                entity_id="downloads",
                occurred_at=now,
                metadata={"result_count": min(limit, len(events))},
            )
        )

        ordered = sorted(events, key=lambda event: event.occurred_at, reverse=True)
        return AuditEventsResponse(events=ordered[:limit])


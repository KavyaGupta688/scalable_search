import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import or_, update

from modules.ai_tag_description_generation.app.db import get_sync_session
from modules.ai_tag_description_generation.app.ingestion_client import IngestionDocument
from modules.ai_tag_description_generation.app.models import EnrichmentTask

logger = logging.getLogger(__name__)

PIPELINE_STAGES = [
    "preprocessing",
    "ocr_extraction",
    "tagging",
    "captioning",
    "quality_safety",
    "metadata_fusion",
    "confidence_validation",
    "persistence",
]


def _uuid_or_none(value: str | None) -> UUID | None:
    return UUID(str(value)) if value else None


def dispatch_or_resume(
    document: IngestionDocument,
) -> Tuple[EnrichmentTask, Optional[str]]:
    """Create, refresh, resume, or skip one idempotent document task."""
    document_id = str(UUID(document.document_id))
    with get_sync_session() as session:
        task = (
            session.query(EnrichmentTask)
            .filter(EnrichmentTask.document_id == document_id)
            .first()
        )
        if task:
            if task.status in (
                "completed",
                "partial",
                "needs_review",
                "failed_terminal",
            ):
                return task, None
            task.run_id = _uuid_or_none(document.run_id)
            task.source_asset_id = _uuid_or_none(document.source_asset_id)
            task.entitlement_id = _uuid_or_none(document.entitlement_id)
            task.source_type = document.source_type
            task.source_ref = document.source_ref
            task.mime_type = document.mime_type
            task.size_bytes = document.size_bytes
            task.checksum_sha256 = document.checksum_sha256
            task.vendor_metadata = document.metadata
            session.commit()
            if task.status in (
                "in_progress",
                "partial",
                "needs_review",
                "queued",
                "queue_failed",
            ):
                return task, PIPELINE_STAGES[
                    0
                ] if task.retry_count <= task.max_retries else None
            return task, None

        task = EnrichmentTask(
            document_id=document_id,
            run_id=_uuid_or_none(document.run_id),
            source_asset_id=_uuid_or_none(document.source_asset_id),
            entitlement_id=_uuid_or_none(document.entitlement_id),
            source_type=document.source_type,
            source_ref=document.source_ref,
            mime_type=document.mime_type,
            size_bytes=document.size_bytes,
            checksum_sha256=document.checksum_sha256,
            vendor_metadata=document.metadata,
            status="queued",
            retry_count=0,
            stage_results={},
        )
        session.add(task)
        session.commit()
        return task, PIPELINE_STAGES[0]


def acquire_lock(document_id: str, worker_id: str, ttl_seconds: int = 300) -> bool:
    normalized_id = str(UUID(document_id))
    now = datetime.now(timezone.utc)
    with get_sync_session() as session:
        result = session.execute(
            update(EnrichmentTask)
            .where(
                EnrichmentTask.document_id == normalized_id,
                or_(
                    EnrichmentTask.locked_by.is_(None),
                    EnrichmentTask.locked_by == worker_id,
                    EnrichmentTask.lock_expires_at < now,
                ),
            )
            .values(
                locked_by=worker_id,
                lock_expires_at=now + timedelta(seconds=ttl_seconds),
            )
        )
        session.commit()
        return result.rowcount == 1


def release_lock(document_id: str, worker_id: str) -> None:
    with get_sync_session() as session:
        task = (
            session.query(EnrichmentTask)
            .filter(EnrichmentTask.document_id == str(UUID(document_id)))
            .first()
        )
        if task and task.locked_by == worker_id:
            task.locked_by = None
            task.lock_expires_at = None
            session.commit()


def increment_retry_count(document_id: str) -> None:
    with get_sync_session() as session:
        task = (
            session.query(EnrichmentTask)
            .filter(EnrichmentTask.document_id == str(UUID(document_id)))
            .first()
        )
        if task:
            task.retry_count += 1
            session.commit()


def update_stage(
    document_id: str,
    stage_name: str,
    status: str,
    error: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    with get_sync_session() as session:
        task = (
            session.query(EnrichmentTask)
            .filter(EnrichmentTask.document_id == str(UUID(document_id)))
            .first()
        )
        if not task:
            return
        stage_data = dict((task.stage_results or {}).get(stage_name, {}))
        stage_data["status"] = status
        if error:
            stage_data["error"] = error
        if duration_ms is not None:
            stage_data["duration_ms"] = duration_ms
        results = dict(task.stage_results or {})
        results[stage_name] = stage_data
        task.stage_results = results
        task.current_stage = stage_name
        session.commit()


def transition_status(
    document_id: str, new_status: str, error_message: Optional[str] = None
) -> None:
    allowed_transitions = {
        "queued": ["in_progress", "queue_failed", "failed_terminal"],
        "queue_failed": ["queued", "in_progress", "failed_terminal"],
        "in_progress": ["completed", "partial", "needs_review", "failed_terminal"],
        "partial": ["in_progress"],
        "needs_review": ["in_progress"],
        "failed_terminal": ["queued"],
        "completed": [],
    }
    with get_sync_session() as session:
        task = (
            session.query(EnrichmentTask)
            .filter(EnrichmentTask.document_id == str(UUID(document_id)))
            .first()
        )
        if not task:
            return
        if new_status in allowed_transitions.get(task.status, []):
            task.status = new_status
            if error_message:
                task.error_message = error_message
            task.updated_at = datetime.now(timezone.utc)
            from modules.shared.delivery import enqueue

            if new_status in (
                "completed",
                "partial",
                "needs_review",
                "failed_terminal",
            ):
                enqueue(
                    session,
                    f"index:{document_id}:{task.updated_at.isoformat()}",
                    "index",
                    {"document_id": document_id},
                )
            enqueue(
                session,
                f"audit:{document_id}:{task.updated_at.isoformat()}",
                "audit",
                {
                    "event_id": f"ai:{document_id}:{task.updated_at.isoformat()}",
                    "action": "AI_" + new_status.upper(),
                    "actor": "ai-worker",
                    "entity_type": "document",
                    "entity_id": document_id,
                    "correlation_id": str(task.run_id) if task.run_id else document_id,
                    "status": "FAILED"
                    if new_status == "failed_terminal"
                    else "SUCCESS",
                },
            )
            session.commit()
        else:
            logger.warning(
                "Invalid state transition attempted: %s -> %s", task.status, new_status
            )

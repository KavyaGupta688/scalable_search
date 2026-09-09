from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import uuid_utils
from botocore.exceptions import ClientError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.config import RetentionSettings, get_settings
from ingestion.models.document import Document
from ingestion.models.retention import LicenseEntitlement, RetentionEvent
from ingestion.monitoring.logging import get_logger
from ingestion.monitoring.metrics import METRICS
from ingestion.retention.policy import build_lifecycle_rules, managed_lifecycle_rule_ids
from ingestion.services.database import get_raw_session
from ingestion.storage.minio_client import MinIOClient

logger = get_logger(__name__)

DELETED_STATUSES = ("deleted_by_reconciler", "already_absent_at_expiry")


@dataclass
class RetentionRunResult:
    due_found: int = 0
    deleted: int = 0
    already_absent: int = 0
    blocked: int = 0
    errors: int = 0
    missing_before_expiry: int = 0
    dry_run_due: int = 0


def _assert_expected_versioning(retention: RetentionSettings, actual: str) -> None:
    expected = retention.expected_bucket_versioning
    if expected != "Any" and actual != expected:
        raise RuntimeError(
            f"MinIO bucket versioning is {actual}, but retention expects {expected}; "
            "refusing lifecycle changes and deletion"
        )


def _is_lock_or_permission_block(exc: Exception) -> bool:
    if not isinstance(exc, ClientError):
        return False
    code = exc.response.get("Error", {}).get("Code", "")
    message = exc.response.get("Error", {}).get("Message", "").lower()
    return code in {"AccessDenied", "InvalidRequest", "MethodNotAllowed"} or any(
        term in message for term in ("legal hold", "object lock", "retention")
    )


def _add_event(
    session: AsyncSession,
    document: Document,
    *,
    outcome: str,
    current_time: datetime,
    details: dict | None = None,
) -> None:
    session.add(
        RetentionEvent(
            id=UUID(str(uuid_utils.uuid7())),
            document_id=document.id,
            entitlement_id=document.entitlement_id,
            event_type="retention_reconciliation",
            outcome=outcome,
            event_at=current_time,
            actor_type="retention_reconciler",
            details=details,
        )
    )


async def install_lifecycle_policy(
    minio: MinIOClient, retention: RetentionSettings
) -> list[dict]:
    """Install only managed lifecycle rules while preserving unrelated rules."""

    if not retention.enabled:
        METRICS.RETENTION_LIFECYCLE_CONFIGURED.set(0)
        logger.info("Retention lifecycle enforcement is disabled")
        return []

    try:
        versioning_status = await minio.get_bucket_versioning_status()
        _assert_expected_versioning(retention, versioning_status)
        object_lock = (
            await minio.get_object_lock_configuration()
            if versioning_status in {"Enabled", "Suspended"}
            else None
        )
        rules = build_lifecycle_rules(
            base_rule_id=retention.lifecycle_rule_id,
            prefix=retention.object_prefix,
            expiration_days=retention.lifecycle_expiration_days,
            noncurrent_days=retention.noncurrent_expiration_days,
            abort_multipart_days=retention.incomplete_multipart_days,
            versioning_status=versioning_status,
        )
        if retention.dry_run:
            METRICS.RETENTION_LIFECYCLE_CONFIGURED.set(0)
            logger.info(
                "Retention lifecycle dry-run; managed rules were not installed",
                extra={
                    "context": {
                        "bucket": minio.bucket,
                        "rules": rules,
                        "versioning_status": versioning_status,
                        "object_lock_enabled": bool(
                            object_lock
                            and object_lock.get("ObjectLockEnabled") == "Enabled"
                        ),
                    }
                },
            )
            return rules

        await minio.apply_managed_lifecycle_rules(
            rules, managed_lifecycle_rule_ids(retention.lifecycle_rule_id)
        )
        METRICS.RETENTION_LIFECYCLE_APPLY_TOTAL.labels(outcome="success").inc()
        METRICS.RETENTION_LIFECYCLE_CONFIGURED.set(1)
        logger.info(
            "Managed MinIO retention lifecycle rules installed",
            extra={
                "context": {
                    "bucket": minio.bucket,
                    "prefix": retention.object_prefix,
                    "rule_ids": [rule["ID"] for rule in rules],
                    "versioning_status": versioning_status,
                }
            },
        )
        return rules
    except Exception:
        METRICS.RETENTION_LIFECYCLE_APPLY_TOTAL.labels(outcome="failure").inc()
        METRICS.RETENTION_LIFECYCLE_CONFIGURED.set(0)
        logger.exception("Failed to install managed MinIO lifecycle rules")
        raise


async def _pending_count(session: AsyncSession, now: datetime) -> int:
    return int(
        await session.scalar(
            select(func.count(Document.id))
            .join(LicenseEntitlement, Document.entitlement_id == LicenseEntitlement.id)
            .where(
                LicenseEntitlement.expires_at <= now,
                Document.retention_status.not_in(DELETED_STATUSES),
            )
        )
        or 0
    )


async def _missing_count(session: AsyncSession) -> int:
    return int(
        await session.scalar(
            select(func.count(Document.id)).where(
                Document.retention_status == "missing_before_expiry"
            )
        )
        or 0
    )


async def reconcile_retention_once(
    *,
    minio: MinIOClient | None = None,
    session: AsyncSession | None = None,
    retention: RetentionSettings | None = None,
    now: datetime | None = None,
) -> RetentionRunResult:
    """Delete due content and retain an append-only database audit trail."""

    started = time.perf_counter()
    settings = retention or get_settings().retention
    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    client = minio or MinIOClient()
    owns_session = session is None
    db = session or await get_raw_session()
    result = RetentionRunResult()

    try:
        if not settings.enabled:
            logger.info("Retention reconciliation disabled")
            return result

        versioning_status = await client.get_bucket_versioning_status()
        _assert_expected_versioning(settings, versioning_status)
        due_query = (
            select(Document)
            .join(LicenseEntitlement, Document.entitlement_id == LicenseEntitlement.id)
            .where(
                LicenseEntitlement.expires_at <= current_time,
                Document.retention_status.in_(
                    ("active", "expiry_due", "deletion_pending", "deletion_failed")
                ),
            )
            .order_by(LicenseEntitlement.expires_at, Document.id)
            .limit(settings.reconciliation_batch_size)
            .with_for_update(skip_locked=True)
        )
        due_documents = list((await db.scalars(due_query)).all())
        result.due_found = len(due_documents)

        for document in due_documents:
            document.last_reconciled_at = current_time
            if settings.dry_run:
                result.dry_run_due += 1
                METRICS.RETENTION_OBJECTS_TOTAL.labels(outcome="dry_run_due").inc()
                continue

            try:
                document.retention_status = "deletion_pending"
                exists = await client.object_exists_including_versions(
                    document.storage_path, versioning_status=versioning_status
                )
                if not exists:
                    document.retention_status = "already_absent_at_expiry"
                    document.deleted_at = current_time
                    _add_event(
                        db,
                        document,
                        outcome="already_absent_at_expiry",
                        current_time=current_time,
                    )
                    result.already_absent += 1
                    METRICS.RETENTION_OBJECTS_TOTAL.labels(
                        outcome="already_absent"
                    ).inc()
                    continue

                deleted_versions = await client.delete_object_and_all_versions(
                    document.storage_path, versioning_status=versioning_status
                )
                if await client.object_exists_including_versions(
                    document.storage_path, versioning_status=versioning_status
                ):
                    raise RuntimeError("object content remains after deletion")

                document.retention_status = "deleted_by_reconciler"
                document.deleted_at = current_time
                _add_event(
                    db,
                    document,
                    outcome="deleted_by_reconciler",
                    current_time=current_time,
                    details={"objects_or_versions_deleted": deleted_versions},
                )
                result.deleted += 1
                METRICS.RETENTION_OBJECTS_TOTAL.labels(outcome="deleted").inc()
            except Exception as exc:
                blocked = _is_lock_or_permission_block(exc)
                document.retention_status = "deletion_failed"
                error_code = "lock_or_permission_block" if blocked else "deletion_error"
                _add_event(
                    db,
                    document,
                    outcome="deletion_failed",
                    current_time=current_time,
                    details={"error_code": error_code, "error_detail": str(exc)},
                )
                if blocked:
                    result.blocked += 1
                    METRICS.RETENTION_OBJECTS_TOTAL.labels(outcome="blocked").inc()
                else:
                    result.errors += 1
                    METRICS.RETENTION_OBJECTS_TOTAL.labels(outcome="error").inc()
                logger.exception(
                    "Expired object deletion was not completed",
                    extra={"document_id": str(document.id)},
                )

        if not settings.dry_run:
            expired_entitlements = {
                document.entitlement_id
                for document in due_documents
                if document.retention_status in DELETED_STATUSES
            }
            if expired_entitlements:
                await db.execute(
                    update(LicenseEntitlement)
                    .where(LicenseEntitlement.id.in_(expired_entitlements))
                    .values(status="expired")
                )

        active_query = (
            select(Document)
            .join(LicenseEntitlement, Document.entitlement_id == LicenseEntitlement.id)
            .where(
                Document.retention_status == "active",
                LicenseEntitlement.expires_at > current_time,
            )
            .order_by(Document.last_reconciled_at.asc().nullsfirst(), Document.id)
            .limit(settings.reconciliation_batch_size)
            .with_for_update(skip_locked=True)
        )
        active_documents = list((await db.scalars(active_query)).all())
        for document in active_documents:
            document.last_reconciled_at = current_time
            try:
                if not await client.object_exists(
                    document.storage_path, version_id=document.object_version_id
                ):
                    document.retention_status = "missing_before_expiry"
                    _add_event(
                        db,
                        document,
                        outcome="missing_before_expiry",
                        current_time=current_time,
                    )
                    result.missing_before_expiry += 1
                    METRICS.RETENTION_OBJECTS_TOTAL.labels(
                        outcome="missing_early"
                    ).inc()
            except Exception as exc:
                _add_event(
                    db,
                    document,
                    outcome="existence_check_failed",
                    current_time=current_time,
                    details={
                        "error_code": "existence_check_failed",
                        "error_detail": str(exc),
                    },
                )
                result.errors += 1
                METRICS.RETENTION_OBJECTS_TOTAL.labels(outcome="check_error").inc()

        await db.commit()
        pending = await _pending_count(db, current_time)
        missing = await _missing_count(db)
        METRICS.RETENTION_EXPIRED_PENDING.set(pending)
        METRICS.RETENTION_ACTIVE_MISSING.set(missing)
        METRICS.RETENTION_RECONCILIATION_RUNS_TOTAL.labels(outcome="success").inc()
        METRICS.RETENTION_LAST_SUCCESS_TIMESTAMP.set(current_time.timestamp())
        logger.info(
            "Retention reconciliation completed",
            extra={
                "context": {
                    **result.__dict__,
                    "expired_pending": pending,
                    "missing": missing,
                }
            },
        )
        return result
    except Exception:
        await db.rollback()
        METRICS.RETENTION_RECONCILIATION_RUNS_TOTAL.labels(outcome="failure").inc()
        logger.exception("Retention reconciliation failed")
        raise
    finally:
        METRICS.RETENTION_RECONCILIATION_DURATION_SECONDS.observe(
            time.perf_counter() - started
        )
        if owns_session:
            await db.close()

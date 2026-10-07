from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.config import RetentionSettings, get_settings
from ingestion.models.retention import LicenseEntitlement
from ingestion.monitoring.logging import get_logger
from ingestion.monitoring.metrics import METRICS
from ingestion.services.database import get_raw_session

logger = get_logger(__name__)


@dataclass
class RetentionRunResult:
    due_found: int = 0
    expired: int = 0
    dry_run_due: int = 0
    errors: int = 0


async def _pending_count(session: AsyncSession, now: datetime) -> int:
    return int(
        await session.scalar(
            select(func.count(LicenseEntitlement.id)).where(
                LicenseEntitlement.status == "active",
                LicenseEntitlement.expires_at <= now,
            )
        )
        or 0
    )


async def _enqueue_search_refresh(db: AsyncSession, entitlements, now: datetime) -> None:
    """Ask Search to re-project documents whose licence status just changed.

    Written in the same transaction as the status change, so the refresh cannot be lost.
    """
    if not entitlements:
        return
    from modules.shared.delivery import enqueue_async
    from ingestion.models.document import Document

    ids = [entitlement.id for entitlement in entitlements]
    document_ids = (
        await db.scalars(select(Document.id).where(Document.entitlement_id.in_(ids)))
    ).all()
    for document_id in document_ids:
        await enqueue_async(
            db,
            f"search-refresh:{document_id}:{now.isoformat()}",
            "search-refresh",
            {"document_id": str(document_id)},
        )


async def reconcile_retention_once(
    *,
    session: AsyncSession | None = None,
    retention: RetentionSettings | None = None,
    now: datetime | None = None,
) -> RetentionRunResult:
    """Record due licence clocks without deleting or blocking vendor content."""

    started = time.perf_counter()
    settings = retention or get_settings().retention
    current_time = (now or datetime.now(UTC)).astimezone(UTC)
    owns_session = session is None
    db = session or await get_raw_session()
    result = RetentionRunResult()

    try:
        if not settings.enabled:
            logger.info("Licence-expiry reconciliation disabled")
            return result

        entitlements = list(
            (
                await db.scalars(
                    select(LicenseEntitlement)
                    .where(
                        LicenseEntitlement.status == "active",
                        LicenseEntitlement.expires_at <= current_time,
                    )
                    .order_by(LicenseEntitlement.expires_at, LicenseEntitlement.id)
                    .limit(settings.reconciliation_batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        result.due_found = len(entitlements)

        if settings.dry_run:
            result.dry_run_due = len(entitlements)
        else:
            for entitlement in entitlements:
                entitlement.status = "expired"
                result.expired += 1
                METRICS.RETENTION_OBJECTS_TOTAL.labels(outcome="expiry_recorded").inc()
            await _enqueue_search_refresh(db, entitlements, current_time)

        await db.commit()
        pending = await _pending_count(db, current_time)
        METRICS.RETENTION_EXPIRED_PENDING.set(pending)
        METRICS.RETENTION_RECONCILIATION_RUNS_TOTAL.labels(outcome="success").inc()
        METRICS.RETENTION_LAST_SUCCESS_TIMESTAMP.set(current_time.timestamp())
        logger.info(
            "Licence-expiry reconciliation completed",
            extra={"context": {**result.__dict__, "expired_pending": pending}},
        )
        return result
    except Exception:
        await db.rollback()
        result.errors += 1
        METRICS.RETENTION_RECONCILIATION_RUNS_TOTAL.labels(outcome="failure").inc()
        logger.exception("Licence-expiry reconciliation failed")
        raise
    finally:
        METRICS.RETENTION_RECONCILIATION_DURATION_SECONDS.observe(time.perf_counter() - started)
        if owns_session:
            await db.close()

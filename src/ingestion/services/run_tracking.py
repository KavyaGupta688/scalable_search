"""Concurrency-safe ingestion run accounting for API enumeration and workers."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.models.ingestion_run import IngestionRun, IngestionRunItem
from ingestion.monitoring.logging import get_logger
from ingestion.monitoring.metrics import METRICS
from ingestion.schemas.job import JobDescriptor, ProcessResult, ProcessingStats


TERMINAL_OUTCOMES = {
    ProcessResult.SUCCESS.value,
    ProcessResult.DUPLICATE.value,
    ProcessResult.SKIPPED.value,
    ProcessResult.REJECTED.value,
    ProcessResult.PERMANENT_ERROR.value,
}

logger = get_logger(__name__)


async def mark_enumeration_started(session: AsyncSession, run_id: UUID) -> None:
    await session.execute(
        update(IngestionRun)
        .where(IngestionRun.id == run_id)
        .values(status="enumerating", enumeration_started_at=datetime.now(UTC))
    )
    await session.commit()


async def mark_enumeration_completed(
    session: AsyncSession,
    run_id: UUID,
    *,
    enumerated_count: int,
    metadata_files_skipped: int,
    duration_seconds: float,
    peak_memory_bytes: int | None,
    enumeration_stats: dict,
) -> None:
    now = datetime.now(UTC)
    await session.execute(
        update(IngestionRun)
        .where(IngestionRun.id == run_id)
        .values(
            status="processing",
            enumeration_completed_at=now,
            enumerated_count=enumerated_count,
            metadata_files_skipped=metadata_files_skipped,
            enumeration_seconds=duration_seconds,
            peak_memory_bytes=peak_memory_bytes,
            enumeration_stats=enumeration_stats,
        )
    )
    await _finish_if_complete(session, run_id, now)
    await session.commit()


async def mark_run_failed(session: AsyncSession, run_id: UUID, error: Exception | str) -> None:
    run = await session.get(IngestionRun, run_id)
    if run is None or run.completed_at is not None:
        return
    now = datetime.now(UTC)
    await session.execute(
        update(IngestionRun)
        .where(IngestionRun.id == run_id)
        .values(status="failed", completed_at=now, error_detail=str(error)[:4000])
    )
    METRICS.RUNS_TOTAL.labels(source_type=run.source_type, status="failed").inc()
    METRICS.RUN_DURATION_SECONDS.labels(source_type=run.source_type).observe(
        max(0.0, (now - run.triggered_at).total_seconds())
    )
    logger.error(
        "Ingestion run failed",
        extra={"run_id": str(run_id), "connector_id": str(run.connector_id)},
    )
    await session.commit()


async def record_transient_retry(
    session: AsyncSession,
    job: JobDescriptor,
    stats: ProcessingStats,
    error: Exception | str,
) -> None:
    if job.run_id is None:
        return
    if await session.get(IngestionRun, job.run_id) is None:
        # Backward compatibility for Kafka messages published before migration 012.
        return
    statement = insert(IngestionRunItem).values(
        run_id=job.run_id,
        source_ref=job.source_ref,
        job_id=job.provisional_id,
        outcome=ProcessResult.TRANSIENT_ERROR.value,
        enumerated_at=job.enumerated_at,
        processing_started_at=stats.processing_started_at,
        attempts=1,
        bytes_processed=stats.bytes_processed,
        stage_seconds=stats.stage_seconds,
        last_error=str(error)[:4000],
    )
    statement = statement.on_conflict_do_update(
        index_elements=[IngestionRunItem.run_id, IngestionRunItem.source_ref],
        set_={
            "outcome": ProcessResult.TRANSIENT_ERROR.value,
            "attempts": IngestionRunItem.attempts + 1,
            "bytes_processed": stats.bytes_processed,
            "stage_seconds": stats.stage_seconds,
            "last_error": str(error)[:4000],
        },
        where=IngestionRunItem.completed_at.is_(None),
    )
    changed = (await session.execute(statement.returning(IngestionRunItem.run_id))).scalar_one_or_none()
    if changed is None:
        return
    await session.execute(
        update(IngestionRun)
        .where(IngestionRun.id == job.run_id)
        .values(
            transient_retry_count=IngestionRun.transient_retry_count + 1,
            bytes_processed=IngestionRun.bytes_processed + stats.bytes_processed,
        )
    )


async def record_terminal_result(
    session: AsyncSession,
    job: JobDescriptor,
    outcome: ProcessResult,
    stats: ProcessingStats,
    error: Exception | str | None = None,
) -> bool:
    """Persist a terminal item and increment its run exactly once."""

    if job.run_id is None:
        return False
    if await session.get(IngestionRun, job.run_id) is None:
        # Backward compatibility for Kafka messages published before migration 012.
        return False
    if outcome.value not in TERMINAL_OUTCOMES:
        raise ValueError(f"Non-terminal run outcome: {outcome.value}")

    now = datetime.now(UTC)
    statement = insert(IngestionRunItem).values(
        run_id=job.run_id,
        source_ref=job.source_ref,
        job_id=job.provisional_id,
        document_id=stats.document_id,
        source_asset_id=stats.source_asset_id,
        outcome=outcome.value,
        enumerated_at=job.enumerated_at,
        processing_started_at=stats.processing_started_at,
        completed_at=now,
        attempts=1,
        bytes_processed=stats.bytes_processed,
        stage_seconds=stats.stage_seconds,
        last_error=str(error)[:4000] if error else None,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[IngestionRunItem.run_id, IngestionRunItem.source_ref],
        set_={
            "document_id": stats.document_id,
            "source_asset_id": stats.source_asset_id,
            "outcome": outcome.value,
            "completed_at": now,
            "attempts": IngestionRunItem.attempts + 1,
            "bytes_processed": stats.bytes_processed,
            "stage_seconds": stats.stage_seconds,
            "last_error": str(error)[:4000] if error else None,
        },
        where=IngestionRunItem.completed_at.is_(None),
    ).returning(IngestionRunItem.run_id)
    recorded = (await session.execute(statement)).scalar_one_or_none() is not None
    if not recorded:
        return False


    counter_name = {
        ProcessResult.SUCCESS: "succeeded_count",
        ProcessResult.DUPLICATE: "duplicate_count",
        ProcessResult.SKIPPED: "skipped_count",
        ProcessResult.REJECTED: "rejected_count",
        ProcessResult.PERMANENT_ERROR: "failed_count",
    }[outcome]
    values = {
        "terminal_count": IngestionRun.terminal_count + 1,
        "bytes_processed": IngestionRun.bytes_processed + stats.bytes_processed,
        counter_name: getattr(IngestionRun, counter_name) + 1,
    }
    await session.execute(update(IngestionRun).where(IngestionRun.id == job.run_id).values(**values))
    await _finish_if_complete(session, job.run_id, now)
    return True


async def add_commit_duration(
    session: AsyncSession, run_id: UUID | None, source_ref: str, seconds: float
) -> None:
    if run_id is None:
        return
    item = await session.get(IngestionRunItem, (run_id, source_ref))
    if item is None:
        return
    stages = dict(item.stage_seconds or {})
    stages["postgresql_commit"] = stages.get("postgresql_commit", 0.0) + seconds
    item.stage_seconds = stages


async def _finish_if_complete(session: AsyncSession, run_id: UUID, now: datetime) -> None:
    run = await session.scalar(
        select(IngestionRun)
        .where(IngestionRun.id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if run is None or run.completed_at is not None or run.enumeration_completed_at is None:
        return
    if run.terminal_count < run.enumerated_count:
        return
    run.status = "completed_with_errors" if run.failed_count or run.rejected_count else "completed"
    run.completed_at = now
    METRICS.RUNS_TOTAL.labels(source_type=run.source_type, status=run.status).inc()
    METRICS.RUN_DURATION_SECONDS.labels(source_type=run.source_type).observe(
        max(0.0, (now - run.triggered_at).total_seconds())
    )
    logger.info(
        "Ingestion run completed",
        extra={
            "run_id": str(run.id),
            "connector_id": str(run.connector_id),
            "outcome": run.status,
            "context": {
                "enumerated": run.enumerated_count,
                "terminal": run.terminal_count,
                "succeeded": run.succeeded_count,
                "duplicates": run.duplicate_count,
                "skipped": run.skipped_count,
                "rejected": run.rejected_count,
                "failed": run.failed_count,
                "bytes_processed": run.bytes_processed,
                "elapsed_seconds": round((now - run.triggered_at).total_seconds(), 3),
            },
        },
    )

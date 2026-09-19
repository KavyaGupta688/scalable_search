"""
Ingestion management endpoints.

Trigger enumeration, check status, and initiate reconciliation sweeps.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.api.auth import RequirePermission
from ingestion.api.deps import get_async_session
from ingestion.models.checkpoint import EnumerationCheckpoint
from ingestion.models.connector import Connector, ConnectorStatus
from ingestion.models.ingestion_run import IngestionRun, IngestionRunItem
from ingestion.monitoring.logging import get_logger
from ingestion.orchestration.enumerator import run_enumeration
from ingestion.reconciliation.sweep import run_reconciliation_sweep
from ingestion.schemas.ingestion_run import IngestionRunItemResponse, IngestionRunResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/ingestion", tags=["Ingestion"])


def _run_response(run: IngestionRun, stage_timings: dict | None = None) -> IngestionRunResponse:
    finished_at = run.completed_at or datetime.now(UTC)
    elapsed = max(0.0, (finished_at - run.triggered_at).total_seconds())
    values = {column.name: getattr(run, column.name) for column in IngestionRun.__table__.columns}
    values.update(
        elapsed_seconds=round(elapsed, 3),
        mib_per_second=round((run.bytes_processed / 1024 / 1024) / elapsed, 3) if elapsed else None,
        objects_per_second=round(run.terminal_count / elapsed, 3) if elapsed else None,
        stage_timings=stage_timings or {},
    )
    return IngestionRunResponse.model_validate(values)


@router.post(
    "/trigger/{connector_id}",
    dependencies=[Depends(RequirePermission("ingestion:trigger"))],
)
async def trigger_ingestion(
    connector_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_session),
):
    """Trigger enumeration for a specific connector."""
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    if connector.archived_at:
        raise HTTPException(409, "Connector is archived")
    if connector.status != ConnectorStatus.VERIFIED:
        raise HTTPException(
            status_code=400,
            detail=f"Connector is not verified (current status: {connector.status.value}). "
            "Run POST /admin/connectors/{id}/test first.",
        )

    run_id = uuid4()
    db.add(
        IngestionRun(
            id=run_id,
            connector_id=connector_id,
            source_type=connector.source_type.value,
            status="queued",
            triggered_at=datetime.now(UTC),
        )
    )
    # The background enumerator opens its own session. Commit here so the run
    # row is visible before that task attempts to update it.
    await db.commit()
    # Starlette awaits async background callables on the application's current
    # event loop.  Do not wrap this in asyncio.run(): SQLAlchemy's async engine
    # and pooled connections belong to the API loop and cannot cross loops.
    background_tasks.add_task(run_enumeration, connector_id, run_id)

    logger.info(
        f"Enumeration triggered for connector {connector_id}",
        extra={
            "connector_id": str(connector_id),
            "context": {"run_id": str(run_id)},
        },
    )
    return {
        "status": "enumeration_triggered",
        "connector_id": str(connector_id),
        "run_id": str(run_id),
    }


@router.get(
    "/runs",
    response_model=list[IngestionRunResponse],
    dependencies=[Depends(RequirePermission("ingestion:trigger"))],
)
async def list_ingestion_runs(
    connector_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_async_session),
):
    query = select(IngestionRun).order_by(IngestionRun.triggered_at.desc()).limit(limit)
    if connector_id is not None:
        query = query.where(IngestionRun.connector_id == connector_id)
    runs = (await db.scalars(query)).all()
    return [_run_response(run) for run in runs]


@router.get(
    "/runs/{run_id}",
    response_model=IngestionRunResponse,
    dependencies=[Depends(RequirePermission("ingestion:trigger"))],
)
async def get_ingestion_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_async_session),
):
    run = await db.get(IngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Ingestion run not found")
    rows = (
        await db.execute(
            text(
                """
                SELECT timing.key AS stage,
                       SUM(CAST(timing.value AS double precision)) AS cumulative_seconds,
                       COUNT(*) AS sample_count
                FROM ingestion_run_items AS item
                CROSS JOIN LATERAL jsonb_each_text(item.stage_seconds) AS timing(key, value)
                WHERE item.run_id = :run_id
                GROUP BY timing.key
                ORDER BY timing.key
                """
            ),
            {"run_id": run_id},
        )
    ).all()
    stage_timings = {
        row.stage: {
            "cumulative_seconds": round(float(row.cumulative_seconds), 6),
            "sample_count": row.sample_count,
            "mean_seconds": round(float(row.cumulative_seconds) / row.sample_count, 6),
        }
        for row in rows
    }
    return _run_response(run, stage_timings)


@router.get(
    "/runs/{run_id}/items",
    response_model=list[IngestionRunItemResponse],
    dependencies=[Depends(RequirePermission("ingestion:trigger"))],
)
async def list_ingestion_run_items(
    run_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_async_session),
):
    if await db.get(IngestionRun, run_id) is None:
        raise HTTPException(status_code=404, detail="Ingestion run not found")
    items = (
        await db.scalars(
            select(IngestionRunItem)
            .where(IngestionRunItem.run_id == run_id)
            .order_by(IngestionRunItem.source_ref)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).all()
    return items


@router.get(
    "/status",
    dependencies=[Depends(RequirePermission("ingestion:trigger"))],
)
async def ingestion_status(
    db: AsyncSession = Depends(get_async_session),
):
    """Get current ingestion status — active enumerations and checkpoints."""
    result = await db.execute(select(EnumerationCheckpoint))
    checkpoints = result.scalars().all()

    return {
        "active_enumerations": len(checkpoints),
        "checkpoints": [
            {
                "connector_id": str(cp.connector_id),
                "continuation_token": cp.continuation_token,
                "last_scanned_path": cp.last_scanned_path,
                "updated_at": cp.updated_at.isoformat() if cp.updated_at else None,
            }
            for cp in checkpoints
        ],
    }


@router.post(
    "/reset-checkpoint/{connector_id}",
    dependencies=[Depends(RequirePermission("ingestion:trigger"))],
)
async def reset_enumeration_checkpoint(
    connector_id: UUID,
    db: AsyncSession = Depends(get_async_session),
):
    """Explicitly start a new test/backfill from the beginning of its scope.

    This removes only the selected connector's continuation token.  It never
    deletes source data or document records; existing output
    remains idempotent on a replay.
    """
    result = await db.execute(select(Connector.id).where(Connector.id == connector_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Connector not found")

    await db.execute(delete(EnumerationCheckpoint).where(EnumerationCheckpoint.connector_id == connector_id))
    await db.commit()
    logger.warning(
        "Enumeration checkpoint reset by API request",
        extra={"connector_id": str(connector_id)},
    )
    return {"status": "checkpoint_reset", "connector_id": str(connector_id)}


@router.post(
    "/reconcile",
    dependencies=[Depends(RequirePermission("ingestion:trigger"))],
)
async def trigger_reconciliation(
    background_tasks: BackgroundTasks,
    connector_id: UUID | None = None,
):
    """Trigger a reconciliation sweep for one or all connectors."""
    background_tasks.add_task(run_reconciliation_sweep, connector_id)

    logger.info(
        f"Reconciliation sweep triggered (connector={connector_id or 'all'})",
        extra={"connector_id": str(connector_id) if connector_id else "all"},
    )
    return {
        "status": "reconciliation_triggered",
        "connector_id": str(connector_id) if connector_id else "all",
    }

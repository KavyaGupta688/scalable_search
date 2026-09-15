"""
Ingestion management endpoints.

Trigger enumeration, check status, and initiate reconciliation sweeps.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.api.auth import RequirePermission
from ingestion.api.deps import get_async_session
from ingestion.models.connector import Connector, ConnectorStatus
from ingestion.models.checkpoint import EnumerationCheckpoint
from ingestion.orchestration.enumerator import run_enumeration
from ingestion.reconciliation.sweep import run_reconciliation_sweep
from ingestion.monitoring.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/ingestion", tags=["Ingestion"])


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

    if connector.status != ConnectorStatus.VERIFIED:
        raise HTTPException(
            status_code=400,
            detail=f"Connector is not verified (current status: {connector.status.value}). "
                   "Run POST /admin/connectors/{id}/test first.",
        )

    run_id = uuid4()
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
    deletes source data, MinIO objects, or document records; existing output
    remains idempotent on a replay.
    """
    result = await db.execute(select(Connector.id).where(Connector.id == connector_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Connector not found")

    await db.execute(
        delete(EnumerationCheckpoint).where(
            EnumerationCheckpoint.connector_id == connector_id
        )
    )
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

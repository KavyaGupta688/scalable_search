from __future__ import annotations

import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert

from ingestion.models.checkpoint import EnumerationCheckpoint
from ingestion.monitoring.logging import get_logger

logger = get_logger(__name__)

async def save_checkpoint(
    session: AsyncSession,
    connector_id: UUID,
    continuation_token: Optional[str] = None,
    last_scanned_path: Optional[str] = None
) -> None:
    """Save or update checkpoint for resumable enumeration."""
    stmt = insert(EnumerationCheckpoint).values(
        connector_id=connector_id,
        continuation_token=continuation_token,
        last_scanned_path=last_scanned_path,
        updated_at=datetime.datetime.utcnow()
    )
    
    stmt = stmt.on_conflict_do_update(
        index_elements=['connector_id'],
        set_={
            'continuation_token': stmt.excluded.continuation_token,
            'last_scanned_path': stmt.excluded.last_scanned_path,
            'updated_at': stmt.excluded.updated_at
        }
    )
    
    await session.execute(stmt)
    await session.commit()
    logger.debug(f"Saved checkpoint for connector {connector_id}")

async def load_checkpoint(session: AsyncSession, connector_id: UUID) -> Optional[EnumerationCheckpoint]:
    """Load the latest checkpoint for a connector."""
    result = await session.execute(
        select(EnumerationCheckpoint).where(EnumerationCheckpoint.connector_id == connector_id)
    )
    return result.scalar_one_or_none()

async def clear_checkpoint(session: AsyncSession, connector_id: UUID) -> None:
    """Clear the checkpoint for a connector."""
    await session.execute(
        delete(EnumerationCheckpoint).where(EnumerationCheckpoint.connector_id == connector_id)
    )
    await session.commit()
    logger.debug(f"Cleared checkpoint for connector {connector_id}")

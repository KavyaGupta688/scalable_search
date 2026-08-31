"""
Connector CRUD API.

All endpoints gated by 'ingestion:configure' permission.
Credentials are stored in Vault — never in Postgres.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.api.auth import RequirePermission, TokenPayload
from ingestion.api.deps import get_async_session, get_vault_service
from ingestion.services.vault import VaultService
from ingestion.connectors import create_connector
from ingestion.models.connector import Connector, ConnectorStatus, SourceType
from ingestion.schemas.connector import (
    ConnectorCreate,
    ConnectorResponse,
    ConnectorTestResponse,
)
from ingestion.services.vault import VaultService
from ingestion.monitoring.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/connectors", tags=["Connectors"])


@router.post(
    "/",
    response_model=ConnectorResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_connector_endpoint(
    connector_in: ConnectorCreate,
    payload: TokenPayload = Depends(RequirePermission("ingestion:configure")),
    db: AsyncSession = Depends(get_async_session),
    vault: VaultService = Depends(get_vault_service),
):
    """Create a new source connector. Stores credentials in Vault, NOT in Postgres."""
    connector_id = uuid4()

    # Extract credentials from the request body
    credentials: dict = {}
    if connector_in.source_type == "S3" and connector_in.s3:
        credentials = {
            "access_key": connector_in.s3.access_key,
            "secret_key": connector_in.s3.secret_key,
        }
    elif connector_in.source_type in ("NAS_SMB", "NAS_NFS") and connector_in.nas:
        credentials = {
            "username": connector_in.nas.username or "",
            "password": connector_in.nas.password or "",
            "domain": connector_in.nas.domain or "",
        }

    # Store credentials in Vault and get the vault path reference
    secret_path = vault.store_connector_secret(connector_id, credentials)

    # Build the Connector model — no raw secrets here
    db_connector = Connector(
        id=connector_id,
        name=connector_in.name,
        source_type=SourceType(connector_in.source_type),
        # S3-specific fields
        endpoint_url=connector_in.s3.endpoint_url if connector_in.s3 else None,
        bucket=connector_in.s3.bucket if connector_in.s3 else None,
        addressing_style=connector_in.s3.addressing_style if connector_in.s3 else None,
        signature_version=connector_in.s3.signature_version if connector_in.s3 else None,
        # NAS-specific fields
        mount_path=connector_in.nas.mount_path if connector_in.nas else None,
        # Vault reference
        secret_path=secret_path,
        # Audit
        created_by=UUID(payload.sub) if payload.sub else uuid4(),
        status=ConnectorStatus.UNVERIFIED,
    )

    db.add(db_connector)
    await db.flush()
    await db.refresh(db_connector)

    logger.info(
        f"Connector created: {connector_id}",
        extra={"connector_id": str(connector_id), "source_type": connector_in.source_type},
    )
    return ConnectorResponse.model_validate(db_connector)


@router.get("/", response_model=List[ConnectorResponse])
async def list_connectors(
    payload: TokenPayload = Depends(RequirePermission("ingestion:configure")),
    db: AsyncSession = Depends(get_async_session),
):
    """List all configured connectors."""
    result = await db.execute(select(Connector).order_by(Connector.created_at.desc()))
    connectors = result.scalars().all()
    return [ConnectorResponse.model_validate(c) for c in connectors]


@router.get("/{connector_id}", response_model=ConnectorResponse)
async def get_connector(
    connector_id: UUID,
    payload: TokenPayload = Depends(RequirePermission("ingestion:configure")),
    db: AsyncSession = Depends(get_async_session),
):
    """Get a single connector's details."""
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    return ConnectorResponse.model_validate(connector)


@router.post("/{connector_id}/test", response_model=ConnectorTestResponse)
async def test_connector(
    connector_id: UUID,
    payload: TokenPayload = Depends(RequirePermission("ingestion:configure")),
    db: AsyncSession = Depends(get_async_session),
    vault: VaultService = Depends(get_vault_service),
):
    """
    Test connectivity to a configured source.

    Instantiates the appropriate SourceConnector, calls test_connection(),
    and updates the connector's status in the database.
    """
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    now = datetime.now(timezone.utc)
    try:
        # Load credentials from Vault
        creds = vault.get_connector_secret(connector.secret_path)
        # Instantiate the real connector
        source_connector = create_connector(connector, creds)
        # Call test_connection
        await source_connector.test_connection()
        connector.status = ConnectorStatus.VERIFIED
        connector.last_verified_at = now
        message = "Connection test successful"
    except Exception as e:
        connector.status = ConnectorStatus.FAILED
        connector.last_verified_at = now
        message = f"Connection test failed: {str(e)}"
        logger.warning(
            f"Connector test failed: {connector_id}",
            extra={"connector_id": str(connector_id), "error": str(e)},
        )

    await db.flush()

    return ConnectorTestResponse(
        connector_id=connector_id,
        status=connector.status.value,
        message=message,
        tested_at=now,
    )


@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connector(
    connector_id: UUID,
    payload: TokenPayload = Depends(RequirePermission("ingestion:configure")),
    db: AsyncSession = Depends(get_async_session),
    vault: VaultService = Depends(get_vault_service),
):
    """Delete a connector and its Vault secrets."""
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    # Delete Vault secret first
    try:
        vault.delete_connector_secret(connector.secret_path)
    except Exception as e:
        logger.warning(f"Failed to delete Vault secret for {connector_id}: {e}")

    await db.delete(connector)
    logger.info(
        f"Connector deleted: {connector_id}",
        extra={"connector_id": str(connector_id)},
    )

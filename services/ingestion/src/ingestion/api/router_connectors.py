"""
Connector CRUD API.

All endpoints gated by 'ingestion:configure' permission.
Credentials are stored in Vault — never in Postgres.
"""

from __future__ import annotations
import asyncio

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import Query, APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from ingestion.models.checkpoint import EnumerationCheckpoint
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.api.auth import RequirePermission, TokenPayload
from ingestion.api.deps import get_async_session, get_vault_service
from ingestion.connectors import create_connector
from ingestion.models.connector import Connector, ConnectorStatus, SourceType
from ingestion.models.document import SourceAsset
from ingestion.models.ingestion_run import IngestionRun
from ingestion.monitoring.logging import get_logger
from ingestion.schemas.connector import (
    ConnectorCreate,
    ConnectorResponse,
    ConnectorTestResponse,
    S3AuthenticationUpdate,
    S3EnumerationScopeUpdate,
)
from ingestion.services.vault import VaultService
from ingestion.config import get_settings

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

    if (
        connector_in.s3
        and connector_in.s3.auth_mode == "static_keys"
        and not get_settings().source_access.allow_static_s3_credentials
    ):
        raise HTTPException(
            status_code=400,
            detail="Static S3 credentials are disabled; configure aws_assume_role",
        )

    # Extract credentials from the request body
    credentials: dict = {}
    if connector_in.source_type == "S3" and connector_in.s3:
        if connector_in.s3.auth_mode == "static_keys":
            credentials = {
                "access_key": connector_in.s3.access_key,
                "secret_key": connector_in.s3.secret_key,
            }
        else:
            credentials = {"external_id": connector_in.s3.external_id or ""}
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
        s3_auth_mode=connector_in.s3.auth_mode if connector_in.s3 else None,
        s3_role_arn=connector_in.s3.role_arn if connector_in.s3 else None,
        s3_session_duration_seconds=(connector_in.s3.session_duration_seconds if connector_in.s3 else None),
        s3_prefix=connector_in.s3.prefix if connector_in.s3 else None,
        source_metadata_mode=connector_in.s3.metadata_mode if connector_in.s3 else "required",
        enumeration_max_objects=(
            connector_in.s3.max_objects if connector_in.s3 else connector_in.nas.max_files if connector_in.nas else None
        ),
        enumeration_page_size=connector_in.s3.page_size if connector_in.s3 else None,
        # NAS-specific fields
        mount_path=connector_in.nas.mount_path if connector_in.nas else None,
        # Vault reference
        secret_path=secret_path,
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


@router.patch("/{connector_id}/s3-scope", response_model=ConnectorResponse)
async def update_s3_enumeration_scope(
    connector_id: UUID,
    scope: S3EnumerationScopeUpdate,
    payload: TokenPayload = Depends(RequirePermission("ingestion:configure")),
    db: AsyncSession = Depends(get_async_session),
):
    """Set a bounded S3 scope without changing the connector's credentials."""
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    if connector.source_type != SourceType.S3:
        raise HTTPException(status_code=400, detail="Enumeration scope is only supported for S3 connectors")

    if connector.archived_at:
        raise HTTPException(409, "Connector is archived")
    await db.execute(delete(EnumerationCheckpoint).where(EnumerationCheckpoint.connector_id == connector_id))
    connector.s3_prefix = scope.prefix
    connector.enumeration_max_objects = scope.max_objects
    connector.enumeration_page_size = scope.page_size
    await db.flush()
    await db.refresh(connector)
    logger.info(
        "S3 enumeration scope updated",
        extra={
            "connector_id": str(connector_id),
            "context": {
                "prefix": scope.prefix,
                "max_objects": scope.max_objects,
                "page_size": scope.page_size,
            },
        },
    )
    return ConnectorResponse.model_validate(connector)


@router.patch("/{connector_id}/s3-auth", response_model=ConnectorResponse)
async def update_s3_authentication(
    connector_id: UUID,
    authentication: S3AuthenticationUpdate,
    payload: TokenPayload = Depends(RequirePermission("ingestion:configure")),
    db: AsyncSession = Depends(get_async_session),
    vault: VaultService = Depends(get_vault_service),
):
    """Switch an existing S3 connector between static and AssumeRole modes."""

    connector = await db.scalar(select(Connector).where(Connector.id == connector_id))
    if connector is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    if connector.source_type != SourceType.S3:
        raise HTTPException(status_code=400, detail="Authentication mode applies only to S3 connectors")
    if authentication.auth_mode == "static_keys" and not get_settings().source_access.allow_static_s3_credentials:
        raise HTTPException(status_code=400, detail="Static S3 credentials are disabled")

    if connector.archived_at:
        raise HTTPException(409, "Connector is archived")
    credentials = (
        {"access_key": authentication.access_key, "secret_key": authentication.secret_key}
        if authentication.auth_mode == "static_keys"
        else {"external_id": authentication.external_id or ""}
    )
    vault.store_connector_secret(connector_id, credentials)
    connector.s3_auth_mode = authentication.auth_mode
    connector.s3_role_arn = authentication.role_arn
    connector.s3_session_duration_seconds = authentication.session_duration_seconds
    connector.status = ConnectorStatus.UNVERIFIED
    await db.flush()
    await db.refresh(connector)
    logger.info(
        "S3 connector authentication replaced",
        extra={
            "connector_id": str(connector_id),
            "context": {"auth_mode": authentication.auth_mode},
        },
    )
    return ConnectorResponse.model_validate(connector)


@router.get("/", response_model=list[ConnectorResponse])
async def list_connectors(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    payload: TokenPayload = Depends(RequirePermission("ingestion:configure")),
    db: AsyncSession = Depends(get_async_session),
):
    """List all configured connectors."""
    result = await db.execute(
        select(Connector)
        .order_by(Connector.name, Connector.id)
        .limit(limit)
        .offset(offset)
        .order_by(Connector.name, Connector.id)
    )
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

    if connector.archived_at:
        raise HTTPException(409, "Connector is archived")
    now = datetime.now(UTC)
    try:
        # Load credentials from Vault
        creds = vault.get_connector_secret(connector.secret_path)
        # Instantiate the real connector
        source_connector = await asyncio.to_thread(create_connector, connector, creds)
        # Call test_connection
        await source_connector.test_connection()
        connector.status = ConnectorStatus.VERIFIED
        message = "Connection test successful"
    except Exception as e:
        connector.status = ConnectorStatus.FAILED
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

    entitlement_exists = await db.scalar(
        select(SourceAsset.id).where(SourceAsset.source_connector_id == connector_id).limit(1)
    )
    run_exists = await db.scalar(select(IngestionRun.id).where(IngestionRun.connector_id == connector_id).limit(1))
    if entitlement_exists is not None or run_exists is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Connector has immutable licence/audit records and cannot be hard-deleted; "
                "archive it to preserve licensed source access instead"
            ),
        )

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


@router.patch("/{connector_id}/archive", response_model=ConnectorResponse)
async def archive_connector(
    connector_id: UUID,
    payload: TokenPayload = Depends(RequirePermission("ingestion:configure")),
    db: AsyncSession = Depends(get_async_session),
):
    connector = await db.get(Connector, connector_id)
    if connector is None:
        raise HTTPException(404, "Connector not found")
    active = await db.scalar(
        select(IngestionRun.id)
        .where(
            IngestionRun.connector_id == connector_id, IngestionRun.status.in_(["queued", "enumerating", "processing"])
        )
        .limit(1)
    )
    if active:
        raise HTTPException(409, "Wait for the active ingestion run to finish before archiving")
    connector.archived_at = connector.archived_at or datetime.now(UTC)
    await db.flush()
    return ConnectorResponse.model_validate(connector)

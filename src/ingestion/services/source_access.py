"""Reusable direct access to vendor-owned S3, SMB, and NFS source assets."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.connectors import SourceConnector, create_connector
from ingestion.connectors.s3 import S3Connector
from ingestion.models.connector import Connector, SourceType
from ingestion.models.document import Document, SourceAsset
from ingestion.models.retention import LicenseEntitlement
from ingestion.schemas.job import JobDescriptor
from ingestion.services.vault import VaultService


class SourceAccessDeniedError(PermissionError):
    """The document licence does not currently permit source access."""


def entitlement_url_lifetime(
    expires_at: datetime, requested_seconds: int, *, now: datetime | None = None
) -> int:
    """Cap a source URL at the legal entitlement boundary."""

    current = now or datetime.now(UTC)
    remaining_seconds = int((expires_at - current).total_seconds())
    if remaining_seconds < 1:
        raise SourceAccessDeniedError("Document licence entitlement has expired")
    return min(requested_seconds, remaining_seconds)


async def require_active_entitlement(
    session: AsyncSession, asset: SourceAsset
) -> LicenseEntitlement:
    entitlement = await session.scalar(
        select(LicenseEntitlement)
        .join(Document, Document.entitlement_id == LicenseEntitlement.id)
        .where(Document.id == asset.document_id)
    )
    now = datetime.now(UTC)
    if entitlement is None:
        raise SourceAccessDeniedError("Document has no licence entitlement")
    if entitlement.status != "active" or entitlement.expires_at <= now:
        raise SourceAccessDeniedError("Document licence entitlement has expired or is inactive")
    return entitlement


async def load_source_connector(
    session: AsyncSession, asset: SourceAsset, vault: VaultService
) -> tuple[Connector, SourceConnector]:
    connector_model = await session.scalar(select(Connector).where(Connector.id == asset.source_connector_id))
    if connector_model is None:
        raise LookupError(f"Connector {asset.source_connector_id} no longer exists")
    credentials = vault.get_connector_secret(connector_model.secret_path)
    return connector_model, create_connector(connector_model, credentials)


def source_asset_job(asset: SourceAsset, connector: Connector) -> JobDescriptor:
    relative_path: str | None = None
    bucket: str | None = None
    object_key: str | None = None

    if connector.source_type == SourceType.S3:
        bucket = connector.bucket
        prefix = f"{bucket}/"
        object_key = (
            asset.source_ref[len(prefix) :]
            if bucket and asset.source_ref.startswith(prefix)
            else asset.source_ref.split("/", 1)[-1]
        )
    elif connector.source_type == SourceType.NAS_NFS:
        relative_path = asset.source_ref
    else:
        normalized = asset.source_ref.replace("\\", "/")
        mount_parts = (connector.mount_path or "").replace("\\", "/").strip("/").split("/")
        source_parts = normalized.strip("/").split("/")
        # UNC contains server/share/root while SMB source_ref contains share/root.
        comparable_prefix = mount_parts[1:] if len(mount_parts) > 1 else mount_parts
        relative_path = "/".join(source_parts[len(comparable_prefix) :])

    return JobDescriptor(
        source_type=connector.source_type.value,
        connector_id=connector.id,
        source_ref=asset.source_ref,
        size_bytes=asset.size_bytes,
        etag=asset.etag,
        version_id=asset.source_version_id,
        bucket=bucket,
        object_key=object_key,
        mount_path=connector.mount_path,
        relative_path=relative_path,
        mtime=asset.source_last_modified_at,
        provisional_id=f"source-asset:{asset.id}",
    )


async def open_source_stream(
    session: AsyncSession, asset: SourceAsset, vault: VaultService
) -> AsyncGenerator[bytes, None]:
    await require_active_entitlement(session, asset)
    connector_model, connector = await load_source_connector(session, asset, vault)
    job = source_asset_job(asset, connector_model)
    async for chunk in connector.open_stream(job):
        yield chunk


async def generate_source_url(
    session: AsyncSession,
    asset: SourceAsset,
    vault: VaultService,
    *,
    expires_in: int = 3600,
) -> tuple[str | None, int | None]:
    entitlement = await require_active_entitlement(session, asset)
    remaining_entitlement_seconds = int(
        (entitlement.expires_at - datetime.now(UTC)).total_seconds()
    )
    expires_in = entitlement_url_lifetime(entitlement.expires_at, expires_in)
    connector_model, connector = await load_source_connector(session, asset, vault)
    if not isinstance(connector, S3Connector):
        return None, None
    job = source_asset_job(asset, connector_model)
    params = {"Bucket": job.bucket, "Key": job.object_key}
    if asset.source_version_id:
        params["VersionId"] = asset.source_version_id
    def create_url() -> tuple[str, int]:
        try:
            client = connector.client_for_entitlement(remaining_entitlement_seconds)
        except PermissionError as exc:
            raise SourceAccessDeniedError(str(exc)) from exc
        actual_expires_in = expires_in
        if connector._credentials_expire_at is not None:
            credential_seconds = int(
                (connector._credentials_expire_at - datetime.now(UTC)).total_seconds()
            )
            actual_expires_in = min(actual_expires_in, max(1, credential_seconds))
        return (
            client.generate_presigned_url(
                "get_object", Params=params, ExpiresIn=actual_expires_in
            ),
            actual_expires_in,
        )

    return await asyncio.to_thread(create_url)

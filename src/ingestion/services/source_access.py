"""Reusable direct access to vendor-owned S3, SMB, and NFS source assets."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.connectors import SourceConnector, create_connector
from ingestion.connectors.s3 import S3Connector
from ingestion.models.connector import Connector, SourceType
from ingestion.models.document import SourceAsset
from ingestion.schemas.job import JobDescriptor
from ingestion.services.vault import VaultService


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
) -> str | None:
    connector_model, connector = await load_source_connector(session, asset, vault)
    if not isinstance(connector, S3Connector):
        return None
    job = source_asset_job(asset, connector_model)
    params = {"Bucket": job.bucket, "Key": job.object_key}
    if asset.source_version_id:
        params["VersionId"] = asset.source_version_id
    return await asyncio.to_thread(
        connector.client.generate_presigned_url,
        "get_object",
        Params=params,
        ExpiresIn=expires_in,
    )

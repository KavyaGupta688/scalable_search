#!/usr/bin/env python3
"""Create one already-expired disposable object for retention E2E testing."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID

import uuid_utils

from ingestion.config import get_settings
from ingestion.models.document import Document
from ingestion.models.retention import LicenseEntitlement
from ingestion.retention.policy import calculate_calendar_expiry
from ingestion.services.database import get_raw_session
from ingestion.storage.minio_client import MinIOClient


async def seed(connector_id: UUID) -> None:
    settings = get_settings()
    if settings.is_production:
        raise RuntimeError("Retention fixtures are forbidden in production")

    minio = MinIOClient()
    versioning = await minio.get_bucket_versioning_status()
    if versioning != "Unversioned":
        raise RuntimeError(f"Fixture expects an unversioned bucket, got {versioning}")

    fixture_id = UUID(str(uuid_utils.uuid7()))
    source_ref = f"retention-fixture/{fixture_id}.txt"
    object_key = f"{connector_id}/{source_ref}"
    content = f"Disposable retention integration fixture {fixture_id}\n".encode()
    checksum = hashlib.sha256(content).hexdigest()
    first_ingested = datetime.now(timezone.utc) - timedelta(days=1461)
    expiry = calculate_calendar_expiry(first_ingested, settings.retention.policy_years)
    if expiry >= datetime.now(timezone.utc):
        raise RuntimeError("Fixture expiry was not in the past")

    session = await get_raw_session()
    uploaded = False
    try:
        await minio.put_object(object_key, content, "text/plain")
        uploaded = True
        entitlement_id = UUID(str(uuid_utils.uuid7()))
        entitlement = LicenseEntitlement(
            id=entitlement_id,
            license_subject_id=f"sha256:{checksum}",
            license_start_at=first_ingested,
            expires_at=expiry,
            policy_code=f"calendar-{settings.retention.policy_years}y-v1",
            status="active",
            revision=1,
            created_at=first_ingested,
        )
        session.add(entitlement)
        await session.flush()
        session.add(
            Document(
                id=fixture_id,
                entitlement_id=entitlement_id,
                checksum_sha256=checksum,
                size_bytes=len(content),
                mime_type="text/plain",
                bucket_name=minio.bucket,
                storage_path=object_key,
                source_connector_id=connector_id,
                source_ref=source_ref,
                retention_status="active",
            )
        )
        await session.commit()
    except Exception:
        await session.rollback()
        if uploaded:
            await minio.delete_object_and_all_versions(
                object_key, versioning_status="Unversioned"
            )
        raise
    finally:
        await session.close()

    print(f"fixture_document_id={fixture_id}")
    print(f"fixture_object_key={object_key}")
    print(f"fixture_expiry={expiry.isoformat()}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--connector-id", type=UUID, required=True)
    args = parser.parse_args()
    asyncio.run(seed(args.connector_id))


if __name__ == "__main__":
    main()

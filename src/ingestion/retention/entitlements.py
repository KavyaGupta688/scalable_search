"""Licence-clock resolution that cannot be reset by re-ingestion."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import uuid_utils
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.models.retention import LicenseEntitlement
from ingestion.retention.policy import calculate_calendar_expiry


def license_subject_id(checksum_sha256: str) -> str:
    """Stable licence identity for identical content across all sources."""

    if len(checksum_sha256) != 64 or any(character not in "0123456789abcdef" for character in checksum_sha256):
        raise ValueError("checksum_sha256 must be a lowercase SHA-256 hex digest")
    return f"sha256:{checksum_sha256}"


async def find_entitlement(session: AsyncSession, checksum_sha256: str) -> LicenseEntitlement | None:
    return await session.scalar(
        select(LicenseEntitlement)
        .where(
            LicenseEntitlement.license_subject_id == license_subject_id(checksum_sha256),
            LicenseEntitlement.status.in_(("active", "expired", "revoked")),
        )
        .order_by(LicenseEntitlement.revision.desc())
        .limit(1)
    )


async def get_or_create_entitlement(
    *,
    session: AsyncSession,
    checksum_sha256: str,
    completed_at: datetime,
    policy_years: int,
) -> LicenseEntitlement:
    """Return the immutable original clock, serialising concurrent first ingestion."""

    subject = license_subject_id(checksum_sha256)
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(subject))))
    existing = await find_entitlement(session, checksum_sha256)
    if existing is not None:
        return existing

    entitlement = LicenseEntitlement(
        id=UUID(str(uuid_utils.uuid7())),
        license_subject_id=subject,
        license_start_at=completed_at,
        expires_at=calculate_calendar_expiry(completed_at, policy_years),
        policy_code=f"calendar-{policy_years}y-v1",
        status="active",
        revision=1,
        created_at=completed_at,
    )
    session.add(entitlement)
    await session.flush()
    return entitlement

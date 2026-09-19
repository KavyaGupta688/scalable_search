from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ingestion.retention.entitlements import license_subject_id
from ingestion.retention.policy import calculate_calendar_expiry


def test_three_year_calendar_expiry_preserves_utc_time() -> None:
    ingested = datetime(2025, 7, 12, 8, 30, 45, tzinfo=UTC)
    assert calculate_calendar_expiry(ingested, 3) == datetime(2028, 7, 12, 8, 30, 45, tzinfo=UTC)


def test_leap_day_expiry_is_february_28() -> None:
    ingested = datetime(2024, 2, 29, 17, 10, tzinfo=UTC)
    assert calculate_calendar_expiry(ingested, 3) == datetime(2027, 2, 28, 17, 10, tzinfo=UTC)


def test_expiry_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        calculate_calendar_expiry(datetime(2025, 1, 1), 3)


def test_license_subject_is_the_content_hash() -> None:
    checksum = "a" * 64
    assert license_subject_id(checksum) == f"sha256:{checksum}"


def test_license_subject_rejects_invalid_checksum() -> None:
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        license_subject_id("not-a-checksum")

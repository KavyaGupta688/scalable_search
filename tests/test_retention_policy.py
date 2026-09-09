from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ingestion.config import RetentionSettings
from ingestion.retention.policy import (
    build_lifecycle_rules,
    calculate_calendar_expiry,
    managed_lifecycle_rule_ids,
)
from ingestion.retention.service import install_lifecycle_policy
from ingestion.retention.entitlements import assert_ingestion_allowed, license_subject_id
from ingestion.storage.minio_client import MinIOClient
from ingestion.worker.validator import PermanentProcessingError
from types import SimpleNamespace


def test_three_year_calendar_expiry_preserves_utc_time() -> None:
    ingested = datetime(2025, 7, 12, 8, 30, 45, tzinfo=timezone.utc)
    assert calculate_calendar_expiry(ingested, 3) == datetime(
        2028, 7, 12, 8, 30, 45, tzinfo=timezone.utc
    )


def test_leap_day_expiry_is_february_28() -> None:
    ingested = datetime(2024, 2, 29, 17, 10, tzinfo=timezone.utc)
    assert calculate_calendar_expiry(ingested, 3) == datetime(
        2027, 2, 28, 17, 10, tzinfo=timezone.utc
    )


def test_expiry_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        calculate_calendar_expiry(datetime(2025, 1, 1), 3)


def test_lifecycle_cannot_be_configured_before_calendar_expiry() -> None:
    with pytest.raises(ValueError, match="could delete content before"):
        RetentionSettings(
            policy_years=3,
            lifecycle_expiration_days=1095,
            noncurrent_expiration_days=1097,
        )


def test_expired_entitlement_blocks_reingestion_clock_reset() -> None:
    now = datetime(2029, 1, 2, tzinfo=timezone.utc)
    entitlement = SimpleNamespace(
        status="active", expires_at=datetime(2029, 1, 1, tzinfo=timezone.utc)
    )
    with pytest.raises(PermanentProcessingError, match="approved entitlement renewal"):
        assert_ingestion_allowed(entitlement, now)


def test_license_subject_is_the_content_hash() -> None:
    checksum = "a" * 64
    assert license_subject_id(checksum) == f"sha256:{checksum}"


def test_license_subject_rejects_invalid_checksum() -> None:
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        license_subject_id("not-a-checksum")


def test_unversioned_lifecycle_rule_generation() -> None:
    rules = build_lifecycle_rules(
        base_rule_id="ingestion-retention-v1",
        prefix="licensed/",
        expiration_days=1097,
        noncurrent_days=1097,
        abort_multipart_days=7,
        versioning_status="Unversioned",
    )
    assert len(rules) == 1
    rule = rules[0]
    assert rule["Filter"] == {"Prefix": "licensed/"}
    assert rule["Expiration"] == {"Days": 1097}
    assert rule["AbortIncompleteMultipartUpload"] == {"DaysAfterInitiation": 7}
    assert "NoncurrentVersionExpiration" not in rule


def test_versioned_lifecycle_rule_generation_covers_all_versions() -> None:
    rules = build_lifecycle_rules(
        base_rule_id="ingestion-retention-v1",
        prefix="",
        expiration_days=1097,
        noncurrent_days=1097,
        abort_multipart_days=7,
        versioning_status="Enabled",
    )
    assert rules[0]["NoncurrentVersionExpiration"] == {"NoncurrentDays": 1097}
    assert rules[1]["Expiration"] == {"ExpiredObjectDeleteMarker": True}


class FakeLifecycleMinio:
    bucket = "test-bucket"

    def __init__(self) -> None:
        self.applied = None

    async def get_bucket_versioning_status(self):
        return "Enabled"

    async def get_object_lock_configuration(self):
        return {"ObjectLockEnabled": "Enabled"}

    async def apply_managed_lifecycle_rules(self, rules, managed_ids):
        self.applied = (rules, set(managed_ids))


@pytest.mark.asyncio
async def test_installer_dry_run_generates_but_does_not_apply_rules() -> None:
    minio = FakeLifecycleMinio()
    settings = RetentionSettings(
        enabled=True, dry_run=True, expected_bucket_versioning="Enabled"
    )
    rules = await install_lifecycle_policy(minio, settings)
    assert rules
    assert minio.applied is None


@pytest.mark.asyncio
async def test_option_a_refuses_a_versioned_bucket() -> None:
    minio = FakeLifecycleMinio()
    settings = RetentionSettings(enabled=True, dry_run=True)
    with pytest.raises(RuntimeError, match="expects Unversioned"):
        await install_lifecycle_policy(minio, settings)


@pytest.mark.asyncio
async def test_installer_applies_managed_ids_without_governance_bypass() -> None:
    minio = FakeLifecycleMinio()
    settings = RetentionSettings(
        enabled=True, dry_run=False, expected_bucket_versioning="Enabled"
    )
    rules = await install_lifecycle_policy(minio, settings)
    assert minio.applied is not None
    assert minio.applied[0] == rules
    assert minio.applied[1] == managed_lifecycle_rule_ids(settings.lifecycle_rule_id)


class FakeBotoLifecycleClient:
    def __init__(self) -> None:
        self.written = None

    def get_bucket_lifecycle_configuration(self, **_kwargs):
        return {
            "Rules": [
                {"ID": "unrelated-rule", "Status": "Enabled", "Filter": {"Prefix": "other/"}},
                {"ID": "ingestion-retention-v1-objects", "Status": "Disabled", "Filter": {"Prefix": ""}},
            ]
        }

    def put_bucket_lifecycle_configuration(self, **kwargs):
        self.written = kwargs["LifecycleConfiguration"]["Rules"]


@pytest.mark.asyncio
async def test_lifecycle_merge_preserves_unmanaged_rules() -> None:
    minio = object.__new__(MinIOClient)
    minio.bucket = "test-bucket"
    minio.client = FakeBotoLifecycleClient()
    desired = build_lifecycle_rules(
        base_rule_id="ingestion-retention-v1",
        prefix="",
        expiration_days=1097,
        noncurrent_days=1097,
        abort_multipart_days=7,
        versioning_status="Enabled",
    )
    await minio.apply_managed_lifecycle_rules(
        desired, managed_lifecycle_rule_ids("ingestion-retention-v1")
    )
    ids = [rule["ID"] for rule in minio.client.written]
    assert ids == [
        "unrelated-rule",
        "ingestion-retention-v1-objects",
        "ingestion-retention-v1-delete-markers",
    ]

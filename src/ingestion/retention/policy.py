from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def calculate_calendar_expiry(ingested_at: datetime, years: int = 3) -> datetime:
    """Return the UTC calendar anniversary; Feb 29 maps to Feb 28."""

    if ingested_at.tzinfo is None or ingested_at.utcoffset() is None:
        raise ValueError("ingested_at must be timezone-aware")
    if years < 1:
        raise ValueError("years must be at least 1")
    utc_value = ingested_at.astimezone(timezone.utc)
    try:
        return utc_value.replace(year=utc_value.year + years)
    except ValueError:
        # The only valid input date that fails year replacement is Feb 29
        # into a non-leap target year. Expiring on Feb 28 is conservative:
        # content is never retained into March without a valid anniversary.
        return utc_value.replace(year=utc_value.year + years, day=28)


def managed_lifecycle_rule_ids(base_rule_id: str) -> set[str]:
    return {f"{base_rule_id}-objects", f"{base_rule_id}-delete-markers"}


def build_lifecycle_rules(
    *,
    base_rule_id: str,
    prefix: str,
    expiration_days: int,
    noncurrent_days: int,
    abort_multipart_days: int,
    versioning_status: str,
) -> list[dict[str, Any]]:
    """Build MinIO/S3-compatible rules without embedding credentials/buckets."""

    if not base_rule_id or len(base_rule_id) > 220:
        raise ValueError("lifecycle rule ID must contain 1-220 characters")
    if min(expiration_days, noncurrent_days, abort_multipart_days) < 1:
        raise ValueError("lifecycle day values must be positive")

    object_rule: dict[str, Any] = {
        "ID": f"{base_rule_id}-objects",
        "Status": "Enabled",
        "Filter": {"Prefix": prefix},
        "Expiration": {"Days": expiration_days},
        "AbortIncompleteMultipartUpload": {
            "DaysAfterInitiation": abort_multipart_days
        },
    }
    rules = [object_rule]
    if versioning_status in {"Enabled", "Suspended"}:
        object_rule["NoncurrentVersionExpiration"] = {
            "NoncurrentDays": noncurrent_days
        }
        rules.append(
            {
                "ID": f"{base_rule_id}-delete-markers",
                "Status": "Enabled",
                "Filter": {"Prefix": prefix},
                "Expiration": {"ExpiredObjectDeleteMarker": True},
            }
        )
    return rules

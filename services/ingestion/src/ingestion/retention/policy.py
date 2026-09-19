from __future__ import annotations

from datetime import UTC, datetime


def calculate_calendar_expiry(ingested_at: datetime, years: int = 3) -> datetime:
    """Return the UTC calendar anniversary; Feb 29 maps to Feb 28."""

    if ingested_at.tzinfo is None or ingested_at.utcoffset() is None:
        raise ValueError("ingested_at must be timezone-aware")
    if years < 1:
        raise ValueError("years must be at least 1")
    utc_value = ingested_at.astimezone(UTC)
    try:
        return utc_value.replace(year=utc_value.year + years)
    except ValueError:
        # The only valid input date that fails year replacement is Feb 29
        # into a non-leap target year. Expiring on Feb 28 is conservative:
        # content is never retained into March without a valid anniversary.
        return utc_value.replace(year=utc_value.year + years, day=28)

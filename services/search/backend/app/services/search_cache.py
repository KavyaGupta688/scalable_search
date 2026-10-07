"""Short-lived Redis caches for expensive, repeatable search work.

Every key includes the catalogue version that modules/shared/indexer.py increments after
each projection, so a newly indexed, changed or revoked document invalidates all cached
entries at once. Cached values hold ranking work only (ids, scores, facet counts), never
access decisions: callers re-load result rows through the SQL visibility gate.

Caching is best effort. With Redis down or slow, every call simply computes.
"""

import asyncio
import hashlib
import json
import logging
import time

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

CATALOG_VERSION_KEY = "search:catalog_version"  # same key as modules/shared/indexer.py
_TIMEOUT = 0.25
_state = {"down_until": 0.0}


async def _client():
    # The in-memory fallback is per process and never sees the indexer's version bumps,
    # so it could serve stale results; only a shared Redis is used for these caches.
    if not settings.SEARCH_CACHE_ENABLED or settings.REDIS_FALLBACK_MEMORY:
        return None
    if time.monotonic() < _state["down_until"]:
        return None
    try:
        from app.db.redis import get_cache_client

        return await asyncio.wait_for(get_cache_client(), _TIMEOUT * 4)
    except Exception:
        _state["down_until"] = time.monotonic() + 30
        return None


def _key(kind, version, parts):
    digest = hashlib.sha256(
        json.dumps(parts, sort_keys=True, default=str).encode()
    ).hexdigest()
    return f"search:cache:{kind}:{version}:{digest}"


async def get(kind, parts):
    """(hit, value) for a cached entry; (False, None) on a miss or any Redis problem."""
    client = await _client()
    if client is None:
        return False, None
    try:
        version = await asyncio.wait_for(client.get(CATALOG_VERSION_KEY), _TIMEOUT) or "0"
        raw = await asyncio.wait_for(client.get(_key(kind, version, parts)), _TIMEOUT)
    except Exception:
        _state["down_until"] = time.monotonic() + 30
        return False, None
    _record(kind, raw is not None)
    return (True, json.loads(raw)) if raw is not None else (False, None)


async def put(kind, parts, value, since=None):
    """Cache `value`, computed from data read at or after `since` (epoch seconds).

    The entry never outlives the next licence expiry after `since`: licences also expire
    by the clock, without any catalogue change, and a cached count must not include a
    document that has since become invisible. If one expired while computing, nothing
    is cached.
    """
    client = await _client()
    if client is None:
        return
    try:
        version = await asyncio.wait_for(client.get(CATALOG_VERSION_KEY), _TIMEOUT) or "0"
        ttl = await _ttl(version, time.time() if since is None else since)
        if ttl < 1:
            return
        await asyncio.wait_for(
            client.set(_key(kind, version, parts), json.dumps(value, default=str), ex=ttl),
            _TIMEOUT,
        )
    except Exception:
        _state["down_until"] = time.monotonic() + 30


# Earliest active licence expiry: {"version", "since", "at"} of the last lookup.
_expiry = {"version": None, "since": None, "at": None, "checked": 0.0}
_NEXT_EXPIRY_SQL = (
    "SELECT extract(epoch FROM min(expires_at)) FROM ingestion.license_entitlements "
    "WHERE status = 'active' AND expires_at > to_timestamp(:since)"
)


async def _ttl(version, since):
    """Seconds an entry computed at `since` may live: the TTL, cut at the next expiry.

    One indexed lookup (idx_entitlements_expiry), reused until the catalogue version
    changes, the found expiry passes, or 30 seconds go by. Returns 0 if unknown.
    """
    now = time.time()
    memo = _expiry
    reusable = (
        memo["version"] == version
        and memo["since"] is not None
        and memo["since"] <= since
        and now - memo["checked"] < 30
        and (memo["at"] is None or memo["at"] > since)
    )
    if not reusable:
        try:
            from sqlalchemy import text
            from app.db.postgres import engine

            async with engine.connect() as conn:
                at = await asyncio.wait_for(
                    conn.scalar(text(_NEXT_EXPIRY_SQL), {"since": since}), _TIMEOUT * 4
                )
        except Exception:
            return 0  # cannot bound the entry's lifetime, so do not cache it
        memo.update(version=version, since=since, at=float(at) if at is not None else None,
                    checked=now)
    ttl = settings.SEARCH_CACHE_TTL_SECONDS
    if memo["at"] is not None:
        ttl = min(ttl, int(memo["at"] - now))
    return ttl


def _record(kind, hit):
    from app.core.metrics import CACHE_REQUESTS

    CACHE_REQUESTS.labels(cache=kind, outcome="hit" if hit else "miss").inc()

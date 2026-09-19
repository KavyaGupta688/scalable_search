import time
import json
import logging
from typing import Any, Optional
import redis.asyncio as aioredis
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class InMemoryCache:
    def __init__(self):
        self._store: dict[
            str, tuple[Any, float]
        ] = {}  # key -> (value, expiry_timestamp)
        self._zsets: dict[str, dict[str, float]] = {}  # key -> {member: score}
        self._counters: dict[str, int] = {}

    async def get(self, key: str) -> Optional[str]:
        if key in self._store:
            val, exp = self._store[key]
            if exp == 0 or exp > time.time():
                return val
            else:
                del self._store[key]
        return None

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        exp = (time.time() + ex) if ex else 0
        self._store[key] = (value, exp)
        return True

    async def incr(self, key: str) -> int:
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    async def zadd(self, name: str, mapping: dict[str, float]):
        if name not in self._zsets:
            self._zsets[name] = {}
        for member, score in mapping.items():
            self._zsets[name][member] = float(score)

    async def zincrby(self, name: str, amount: float, value: str):
        if name not in self._zsets:
            self._zsets[name] = {}
        self._zsets[name][value] = self._zsets[name].get(value, 0.0) + amount

    async def zrevrange(
        self, name: str, start: int, end: int, withscores: bool = False
    ):
        if name not in self._zsets:
            return []
        sorted_items = sorted(
            self._zsets[name].items(), key=lambda x: x[1], reverse=True
        )
        slice_items = sorted_items[start : (end + 1) if end != -1 else None]
        if withscores:
            return slice_items
        return [item[0] for item in slice_items]

    async def delete(self, *keys: str):
        for k in keys:
            self._store.pop(k, None)
            self._zsets.pop(k, None)
            self._counters.pop(k, None)


_redis_client = None
_in_memory_cache = InMemoryCache()


async def get_cache_client():
    global _redis_client
    if settings.REDIS_FALLBACK_MEMORY:
        return _in_memory_cache

    if _redis_client is None:
        try:
            client = aioredis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
            )
            await client.ping()
            _redis_client = client
            logger.info("Connected to Redis server successfully.")
        except Exception as e:
            logger.warning(
                f"Could not connect to Redis ({e}). Falling back to InMemoryCache."
            )
            raise RuntimeError("Redis is unavailable") from e
    return _redis_client

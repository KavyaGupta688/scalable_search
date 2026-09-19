"""Redis clients and non-mutating connectivity checks."""

from dataclasses import dataclass

import redis

from modules.ai_tag_description_generation.app.config import settings


@dataclass(frozen=True)
class RedisConnectionStatus:
    broker: bool
    result_backend: bool
    events: bool

    @property
    def healthy(self) -> bool:
        return self.broker and self.result_backend and self.events


def create_redis_client(url: str) -> redis.Redis:
    return redis.Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=3,
        health_check_interval=30,
    )


event_redis_client = create_redis_client(settings.EVENT_REDIS_URL)


def check_redis_connections() -> RedisConnectionStatus:
    """Ping each configured Redis role without returning URLs or secrets."""
    return RedisConnectionStatus(
        broker=bool(create_redis_client(settings.CELERY_BROKER_URL).ping()),
        result_backend=bool(create_redis_client(settings.CELERY_RESULT_BACKEND).ping()),
        events=bool(event_redis_client.ping()),
    )

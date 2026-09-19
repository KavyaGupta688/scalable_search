"""Read-only connectivity checks for AI integration dependencies."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import httpx
import redis
from kafka import KafkaConsumer
from qdrant_client import QdrantClient
from sqlalchemy import text

from modules.ai_tag_description_generation.app.config import settings
from modules.ai_tag_description_generation.app.db import async_engine, sync_engine
from modules.ai_tag_description_generation.app.kafka_consumer import _kafka_security


def check(name: str, operation) -> bool:
    try:
        detail = operation()
    except Exception as exc:
        print(f"FAIL  {name}: {type(exc).__name__}: {exc}")
        return False
    print(f"PASS  {name}{': ' + detail if detail else ''}")
    return True


def main() -> int:
    results: list[bool] = []

    def postgres() -> str:
        with sync_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return "SELECT 1 succeeded"

    results.append(check("PostgreSQL", postgres))

    def async_postgres() -> str:
        async def query() -> None:
            async with async_engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            await async_engine.dispose()

        asyncio.run(query())
        return "async SELECT 1 succeeded"

    results.append(check("PostgreSQL async driver", async_postgres))

    def ingestion_api() -> str:
        response = httpx.get(
            f"{settings.INGESTION_API_BASE_URL.rstrip('/')}/health",
            timeout=settings.INGESTION_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return "health endpoint reachable"

    results.append(check("Ingestion API", ingestion_api))

    def kafka() -> str:
        consumer = KafkaConsumer(
            bootstrap_servers=[item.strip() for item in settings.KAFKA_BOOTSTRAP_SERVERS.split(",")],
            consumer_timeout_ms=3000,
            request_timeout_ms=5000,
            api_version_auto_timeout_ms=5000,
            **_kafka_security(),
        )
        topics = consumer.topics()
        consumer.close()
        state = "present" if settings.KAFKA_AI_TOPIC in topics else "missing"
        return f"reachable; topic '{settings.KAFKA_AI_TOPIC}' is {state}"

    results.append(check("Kafka", kafka))

    def qdrant() -> str:
        client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
        names = {item.name for item in client.get_collections().collections}
        state = "present" if settings.QDRANT_COLLECTION_NAME in names else "missing"
        return f"reachable; collection '{settings.QDRANT_COLLECTION_NAME}' is {state}"

    results.append(check("Qdrant", qdrant))
    results.append(
        check(
            "Redis",
            lambda: "PING succeeded" if redis.Redis.from_url(settings.REDIS_URL).ping() else "PING returned false",
        )
    )
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())

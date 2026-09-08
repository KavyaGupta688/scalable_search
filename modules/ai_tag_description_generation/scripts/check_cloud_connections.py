"""Read-only connectivity checks for the configured cloud services.

Run from the repository root after creating
``modules/ai_tag_description_generation/.env``. This script never creates
tables, collections, buckets, tasks, vectors, or Redis keys.
"""
from __future__ import annotations

import sys
import asyncio

import redis
from minio import Minio
from qdrant_client import QdrantClient
from sqlalchemy import text

from modules.ai_tag_description_generation.app.config import settings
from modules.ai_tag_description_generation.app.db import async_engine, sync_engine


def check(name: str, operation) -> bool:
    try:
        detail = operation()
    except Exception as exc:  # Report all failures without exposing secrets.
        print(f"FAIL  {name}: {type(exc).__name__}: {exc}")
        return False
    print(f"PASS  {name}{': ' + detail if detail else ''}")
    return True


def minio_client() -> Minio:
    endpoint = settings.MINIO_ENDPOINT.removeprefix("https://").removeprefix("http://").rstrip("/")
    secure = settings.MINIO_SECURE or settings.MINIO_ENDPOINT.startswith("https://")
    return Minio(
        endpoint,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=secure,
    )


def main() -> int:
    results = []

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

    def qdrant() -> str:
        client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
        collection_names = {item.name for item in client.get_collections().collections}
        state = "present" if settings.QDRANT_COLLECTION_NAME in collection_names else "missing"
        return f"reachable; collection '{settings.QDRANT_COLLECTION_NAME}' is {state}"

    results.append(check("Qdrant", qdrant))
    results.append(check("Redis", lambda: "PING succeeded" if redis.Redis.from_url(settings.REDIS_URL).ping() else "PING returned false"))

    if all((settings.MINIO_ENDPOINT, settings.MINIO_ACCESS_KEY, settings.MINIO_SECRET_KEY)):
        results.append(check("MinIO", lambda: f"reachable; {len(minio_client().list_buckets())} bucket(s) visible"))
    else:
        print("SKIP  MinIO: credentials are not configured")

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())

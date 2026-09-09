"""
FastAPI dependency injection for shared services.

Provides singleton instances of Vault, MinIO, and Kafka producer
for use across API routers via FastAPI's Depends() system.
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.config import get_settings
from ingestion.services.database import get_async_session
from ingestion.services.vault import VaultService
from ingestion.storage.minio_client import MinIOClient
from ingestion.services.kafka import create_producer

from confluent_kafka import Producer


# ── Singletons ──────────────────────────────────────────────────────

_vault_service: VaultService | None = None
_minio_client: MinIOClient | None = None
_kafka_producer: Producer | None = None


def get_vault_service() -> VaultService:
    """Singleton VaultService. Initializes on first call."""
    global _vault_service
    if _vault_service is None:
        _vault_service = VaultService()
    return _vault_service


def get_minio_client() -> MinIOClient:
    """Singleton MinIOClient. Initializes on first call."""
    global _minio_client
    if _minio_client is None:
        _minio_client = MinIOClient()
    return _minio_client


def get_kafka_producer() -> Producer:
    """Singleton Kafka producer. Initializes on first call."""
    global _kafka_producer
    if _kafka_producer is None:
        settings = get_settings()
        _kafka_producer = create_producer(settings.kafka)
    return _kafka_producer


# Re-export the DB session dependency for convenience
__all__ = [
    "get_async_session",
    "get_vault_service",
    "get_minio_client",
    "get_kafka_producer",
]

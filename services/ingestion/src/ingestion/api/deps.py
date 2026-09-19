"""
FastAPI dependency injection for shared services.

Provides singleton instances of Vault and Kafka producer
for use across API routers via FastAPI's Depends() system.
"""

from __future__ import annotations

from confluent_kafka import Producer

from ingestion.config import get_settings
from ingestion.services.database import get_async_session
from ingestion.services.kafka import create_producer
from ingestion.services.vault import VaultService

# ── Singletons ──────────────────────────────────────────────────────

_vault_service: VaultService | None = None
_kafka_producer: Producer | None = None


def get_vault_service() -> VaultService:
    """Singleton VaultService. Initializes on first call."""
    global _vault_service
    if _vault_service is None:
        _vault_service = VaultService()
    return _vault_service


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
    "get_kafka_producer",
]

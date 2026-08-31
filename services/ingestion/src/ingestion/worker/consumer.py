"""
Kafka consumer that dispatches jobs to the streaming worker processor.

Implements manual offset commit, dead-letter routing, circuit breaker
checks, and connector instance caching.
"""

from __future__ import annotations

import asyncio
import json
import signal
from typing import Dict, Any, Optional
from uuid import UUID

from sqlalchemy import select

from ingestion.config import get_settings
from ingestion.services.database import get_raw_session
from ingestion.services.kafka import create_consumer, create_producer, publish_to_dead_letter
from ingestion.services.vault import VaultService
from ingestion.models.connector import Connector
from ingestion.connectors import create_connector, SourceConnector
from ingestion.worker.processor import process_job
from ingestion.worker.validator import PermanentProcessingError, TransientProcessingError
from ingestion.worker.circuit_breaker import MinIOCircuitBreaker
from ingestion.storage.minio_client import MinIOClient
from ingestion.schemas.job import JobDescriptor, ProcessResult
from ingestion.monitoring.logging import get_logger
from ingestion.monitoring.metrics import METRICS

from confluent_kafka import KafkaError

logger = get_logger(__name__)

# Global shutdown flag
_shutdown_requested = False


def _handle_signal(signum, frame):
    """Signal handler for graceful shutdown."""
    global _shutdown_requested
    _shutdown_requested = True
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")


async def run_consumer():
    """
    Main Kafka consumer loop.

    For each job message:
    1. Deserialize JobDescriptor
    2. Load connector (cached) from DB + Vault
    3. Check circuit breaker
    4. Call process_job()
    5. Commit offset on success/permanent failure, skip on transient failure
    """
    global _shutdown_requested

    # Register signal handlers
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    settings = get_settings()
    consumer = create_consumer(settings.kafka, group_id=settings.kafka.consumer_group)
    consumer.subscribe([settings.kafka.ingestion_topic])

    dlq_producer = create_producer(settings.kafka)
    vault_service = VaultService()
    minio_client = MinIOClient()
    circuit_breaker = MinIOCircuitBreaker()

    # Cache connector instances to avoid re-creating for every message
    connector_cache: Dict[UUID, SourceConnector] = {}

    logger.info(
        "Ingestion worker started",
        extra={
            "consumer_group": settings.kafka.consumer_group,
            "topic": settings.kafka.ingestion_topic,
        },
    )

    try:
        while not _shutdown_requested:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                else:
                    logger.error(f"Consumer error: {msg.error()}")
                    continue

            # Parse job descriptor
            try:
                job_data = json.loads(msg.value().decode("utf-8"))
                job = JobDescriptor(**job_data)
            except Exception as e:
                logger.error(
                    f"Failed to deserialize job message: {e}",
                    extra={"raw_value": msg.value()[:200] if msg.value() else None},
                )
                # Commit to skip malformed messages
                consumer.commit(message=msg, asynchronous=False)
                continue

            # Check circuit breaker — if open, pause consumption
            if circuit_breaker.is_open:
                logger.warning(
                    "Circuit breaker is OPEN, pausing consumption for 5s",
                    extra={"connector_id": str(job.connector_id)},
                )
                METRICS.CIRCUIT_BREAKER_STATE.set(1)
                await asyncio.sleep(5.0)
                continue

            # Get or create connector instance
            connector = connector_cache.get(job.connector_id)
            if connector is None:
                try:
                    session = await get_raw_session()
                    try:
                        result = await session.execute(
                            select(Connector).where(Connector.id == job.connector_id)
                        )
                        connector_model = result.scalar_one_or_none()
                        if not connector_model:
                            logger.error(
                                f"Connector {job.connector_id} not found in DB",
                                extra={"connector_id": str(job.connector_id)},
                            )
                            consumer.commit(message=msg, asynchronous=False)
                            continue

                        creds = vault_service.get_connector_secret(connector_model.secret_path)
                        connector = create_connector(connector_model, creds)
                        connector_cache[job.connector_id] = connector
                    finally:
                        await session.close()
                except Exception as e:
                    logger.error(
                        f"Failed to initialize connector: {e}",
                        extra={"connector_id": str(job.connector_id)},
                    )
                    await asyncio.sleep(2.0)
                    continue

            # Process the job
            session = await get_raw_session()
            try:
                result = await process_job(
                    job=job,
                    connector=connector,
                    session=session,
                    minio_client=minio_client,
                    producer=dlq_producer,
                )

                if result in (ProcessResult.SUCCESS, ProcessResult.DUPLICATE, ProcessResult.SKIPPED):
                    await session.commit()
                    consumer.commit(message=msg, asynchronous=False)
                    METRICS.FILES_PROCESSED_TOTAL.labels(
                        source_type=job.source_type, outcome=result.value
                    ).inc()
                    logger.info(
                        f"Job completed: {result.value}",
                        extra={
                            "job_id": job.provisional_id,
                            "source_type": job.source_type,
                            "source_ref": job.source_ref,
                            "outcome": result.value,
                        },
                    )
                elif result == ProcessResult.REJECTED:
                    await session.commit()
                    publish_to_dead_letter(
                        dlq_producer, settings.kafka.dead_letter_topic, msg,
                        PermanentProcessingError(f"MIME type rejected for {job.source_ref}")
                    )
                    consumer.commit(message=msg, asynchronous=False)
                    METRICS.FILES_FAILED_TOTAL.labels(
                        source_type=job.source_type, failure_type="mime_rejected"
                    ).inc()

            except PermanentProcessingError as e:
                await session.rollback()
                logger.error(
                    f"Permanent error processing job: {e}",
                    extra={
                        "job_id": job.provisional_id,
                        "source_ref": job.source_ref,
                        "outcome": "permanent_error",
                    },
                )
                publish_to_dead_letter(
                    dlq_producer, settings.kafka.dead_letter_topic, msg, e
                )
                consumer.commit(message=msg, asynchronous=False)
                METRICS.FILES_FAILED_TOTAL.labels(
                    source_type=job.source_type, failure_type="permanent"
                ).inc()

            except TransientProcessingError as e:
                await session.rollback()
                logger.warning(
                    f"Transient error, will retry: {e}",
                    extra={
                        "job_id": job.provisional_id,
                        "source_ref": job.source_ref,
                        "outcome": "transient_error",
                    },
                )
                # Do NOT commit offset — message will be redelivered
                await asyncio.sleep(2.0)

            except Exception as e:
                await session.rollback()
                logger.error(
                    f"Unexpected error processing job: {e}",
                    extra={"job_id": job.provisional_id},
                )
                await asyncio.sleep(2.0)

            finally:
                await session.close()

    except asyncio.CancelledError:
        logger.info("Consumer loop cancelled")
    finally:
        consumer.close()
        dlq_producer.flush()
        logger.info("Consumer shutdown complete")

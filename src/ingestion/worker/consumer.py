"""
Kafka consumer that dispatches jobs to the streaming worker processor.

Implements manual offset commit, dead-letter routing, circuit breaker
checks, and connector instance caching.
"""

from __future__ import annotations

import asyncio
import json
import signal
import time
from datetime import datetime, timezone
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

from confluent_kafka import KafkaError, TopicPartition

logger = get_logger(__name__)


async def _safe_rollback(session) -> None:
    """Rollback without crashing the consumer if the DB connection died."""
    try:
        await session.rollback()
    except Exception as rollback_error:
        logger.warning("Database rollback failed after connection loss: %s", rollback_error)


async def _retry_current_message(consumer, msg, delay_seconds: float = 2.0) -> None:
    """Seek back before retrying so a later commit cannot skip this record."""
    consumer.seek(TopicPartition(msg.topic(), msg.partition(), msg.offset()))
    await asyncio.sleep(delay_seconds)

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

            if job.enumerated_at is not None:
                queue_wait = max(
                    0.0,
                    (datetime.now(timezone.utc) - job.enumerated_at).total_seconds(),
                )
                METRICS.PROCESSING_DURATION_SECONDS.labels(
                    source_type=job.source_type, stage="queue_wait"
                ).observe(queue_wait)

            # Check circuit breaker — if open, pause consumption
            if circuit_breaker.is_open:
                logger.warning(
                    "Circuit breaker is OPEN, pausing consumption for 5s",
                    extra={"connector_id": str(job.connector_id)},
                )
                METRICS.CIRCUIT_BREAKER_STATE.set(1)
                await _retry_current_message(consumer, msg, 5.0)
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
                    await _retry_current_message(consumer, msg)
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
                    commit_started = time.perf_counter()
                    await session.commit()
                    METRICS.PROCESSING_DURATION_SECONDS.labels(
                        source_type=job.source_type, stage="postgresql_commit"
                    ).observe(time.perf_counter() - commit_started)
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
                            "run_id": str(job.run_id) if job.run_id else None,
                        },
                    )
                elif result == ProcessResult.REJECTED:
                    commit_started = time.perf_counter()
                    await session.commit()
                    METRICS.PROCESSING_DURATION_SECONDS.labels(
                        source_type=job.source_type, stage="postgresql_commit"
                    ).observe(time.perf_counter() - commit_started)
                    publish_to_dead_letter(
                        dlq_producer, settings.kafka.dead_letter_topic, msg,
                        PermanentProcessingError(f"MIME type rejected for {job.source_ref}")
                    )
                    consumer.commit(message=msg, asynchronous=False)
                    METRICS.FILES_FAILED_TOTAL.labels(
                        source_type=job.source_type, failure_type="mime_rejected"
                    ).inc()

            except PermanentProcessingError as e:
                await _safe_rollback(session)
                logger.error(
                    f"Permanent error processing job: {e}",
                    extra={
                        "job_id": job.provisional_id,
                        "source_ref": job.source_ref,
                        "outcome": "permanent_error",
                        "run_id": str(job.run_id) if job.run_id else None,
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
                await _safe_rollback(session)
                logger.warning(
                    f"Transient error, will retry: {e}",
                    extra={
                        "job_id": job.provisional_id,
                        "source_ref": job.source_ref,
                        "outcome": "transient_error",
                        "run_id": str(job.run_id) if job.run_id else None,
                    },
                )
                # Do NOT commit offset — message will be redelivered
                await _retry_current_message(consumer, msg)

            except Exception as e:
                await _safe_rollback(session)
                logger.error(
                    f"Unexpected error processing job: {e}",
                    extra={"job_id": job.provisional_id},
                )
                await _retry_current_message(consumer, msg)

            finally:
                await session.close()

    except asyncio.CancelledError:
        logger.info("Consumer loop cancelled")
    finally:
        consumer.close()
        dlq_producer.flush()
        logger.info("Consumer shutdown complete")

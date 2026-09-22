"""
Enumeration loop that discovers files in a source and publishes
jobs to the Kafka ingestion-jobs topic.

Supports resumable enumeration via checkpointing and retries
transient errors with exponential backoff.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from ingestion.config import get_settings
from ingestion.services.database import get_raw_session
from ingestion.services.vault import VaultService
from ingestion.services.kafka import create_producer, publish_job
from ingestion.models.connector import Connector
from ingestion.connectors import create_connector
from ingestion.connectors.base import TransientConnectorError, PermanentConnectorError
from ingestion.orchestration.checkpointing import load_checkpoint, save_checkpoint, clear_checkpoint
from ingestion.monitoring.logging import get_logger
from ingestion.monitoring.metrics import METRICS
from ingestion.storage.source_metadata import is_metadata_control_file
from ingestion.services.run_tracking import (
    mark_enumeration_completed,
    mark_enumeration_started,
    mark_run_failed,
)

try:  # ``resource`` is available in the Linux worker container, not Windows.
    import resource
except ImportError:  # pragma: no cover - Windows development host
    resource = None

logger = get_logger(__name__)


async def run_enumeration(connector_id: UUID, run_id: UUID | None = None) -> None:
    """
    Main enumeration loop:
    1. Load connector + credentials
    2. Resume from last checkpoint if any
    3. Iterate source files, publish each as a Kafka job
    4. Persist checkpoints periodically
    5. Clear checkpoint on successful completion
    """
    start_time = time.perf_counter()
    files_enumerated = 0
    metadata_files_skipped = 0
    settings = get_settings()

    session = await get_raw_session()

    try:
        # Load connector from DB
        result = await session.execute(select(Connector).where(Connector.id == connector_id))
        connector_model = result.scalar_one_or_none()

        if not connector_model:
            logger.error(f"Connector {connector_id} not found")
            if run_id is not None:
                await mark_run_failed(session, run_id, "Connector not found")
            return

        if run_id is not None:
            await mark_enumeration_started(session, run_id)

        # Load credentials from Vault
        vault_service = VaultService()
        creds = vault_service.get_connector_secret(connector_model.secret_path)

        # Instantiate the source connector
        connector_instance = await asyncio.to_thread(create_connector, connector_model, creds)

        # Create Kafka producer
        producer = create_producer(settings.kafka)

        # Load last checkpoint for resumption
        checkpoint_model = await load_checkpoint(session, connector_id)
        checkpoint_token = checkpoint_model.continuation_token if checkpoint_model else None

        logger.info(
            f"Starting enumeration for connector {connector_id}",
            extra={
                "connector_id": str(connector_id),
                "context": {
                    "run_id": str(run_id) if run_id else None,
                    "has_checkpoint": checkpoint_token is not None,
                },
            },
        )

        max_retries = 5
        base_delay = 2

        async for job_descriptor, new_checkpoint_token in connector_instance.enumerate(checkpoint_token):
            job_descriptor.run_id = run_id
            job_descriptor.enumerated_at = datetime.now(timezone.utc)
            if is_metadata_control_file(job_descriptor, getattr(connector_instance, "metadata_mode", None)):
                metadata_files_skipped += 1
                if new_checkpoint_token is not None:
                    undelivered = await asyncio.to_thread(producer.flush, 30)
                    if undelivered:
                        raise TransientConnectorError(
                            f"Kafka did not deliver {undelivered} jobs before checkpointing"
                        )
                    await save_checkpoint(
                        session, connector_id, continuation_token=new_checkpoint_token
                    )
                    await session.commit()
                continue
            retry_count = 0
            while True:
                try:
                    publish_job(producer, settings.kafka.ingestion_topic, job_descriptor)
                    files_enumerated += 1

                    METRICS.FILES_PROCESSED_TOTAL.labels(
                        source_type=job_descriptor.source_type, outcome="enumerated"
                    ).inc()

                    if new_checkpoint_token is not None:
                        # Do not advance the database checkpoint until every
                        # jobs from this checkpoint interval have been
                        # accepted by Kafka. This makes restarts at-least-once:
                        # a failure replays at most one configured interval
                        # instead of losing unflushed jobs.
                        undelivered = await asyncio.to_thread(producer.flush, 30)
                        if undelivered:
                            raise TransientConnectorError(
                                f"Kafka did not deliver {undelivered} jobs before checkpointing"
                            )
                        await save_checkpoint(
                            session, connector_id, continuation_token=new_checkpoint_token
                        )
                        await session.commit()
                    break

                except TransientConnectorError as e:
                    if retry_count >= max_retries:
                        logger.error(f"Max retries reached for transient error: {e}")
                        raise
                    delay = base_delay * (2 ** retry_count)
                    logger.warning(
                        f"Transient error during enumeration, retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                    retry_count += 1

        # Flush producer and clear checkpoint on completion
        undelivered = await asyncio.to_thread(producer.flush, 30)
        if undelivered:
            raise TransientConnectorError(
                f"Kafka did not deliver {undelivered} jobs at enumeration completion"
            )
        await clear_checkpoint(session, connector_id)
        await session.commit()

        duration = time.perf_counter() - start_time
        METRICS.PROCESSING_DURATION_SECONDS.labels(
            source_type=connector_model.source_type.value, stage="enumeration_total"
        ).observe(duration)
        try:
            # Docker runs on Linux, where ru_maxrss is KiB.  This is peak RSS
            # for the process, useful when comparing bounded streaming to the
            # previous all-pages-in-memory implementation.
            peak_memory_bytes = (
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
                if resource
                else None
            )
            if peak_memory_bytes is not None:
                METRICS.PROCESS_MEMORY_PEAK_BYTES.set(peak_memory_bytes)
        except (AttributeError, OSError):
            peak_memory_bytes = None

        enumeration_stats = getattr(connector_instance, "last_enumeration_stats", {})
        if run_id is not None:
            await mark_enumeration_completed(
                session,
                run_id,
                enumerated_count=files_enumerated,
                metadata_files_skipped=metadata_files_skipped,
                duration_seconds=duration,
                peak_memory_bytes=peak_memory_bytes,
                enumeration_stats=enumeration_stats,
            )
        logger.info(
            f"Enumeration completed for connector {connector_id}",
            extra={
                "connector_id": str(connector_id),
                "context": {
                    "files_enumerated": files_enumerated,
                    "metadata_files_skipped": metadata_files_skipped,
                    "run_id": str(run_id) if run_id else None,
                    "duration_seconds": round(duration, 3),
                    "enumeration_stats": enumeration_stats,
                    "peak_memory_bytes": peak_memory_bytes,
                },
            },
        )

    except PermanentConnectorError as e:
        await session.rollback()
        if run_id is not None:
            await mark_run_failed(session, run_id, e)
        logger.error(
            f"Permanent error during enumeration for connector {connector_id}: {e}",
            extra={"connector_id": str(connector_id)},
        )
    except Exception as e:
        await session.rollback()
        if run_id is not None:
            await mark_run_failed(session, run_id, e)
        logger.error(
            f"Unexpected error during enumeration for connector {connector_id}: {e}",
            extra={"connector_id": str(connector_id)},
        )
    finally:
        await session.close()

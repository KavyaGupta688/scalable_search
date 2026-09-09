"""
Enumeration loop that discovers files in a source and publishes
jobs to the Kafka ingestion-jobs topic.

Supports resumable enumeration via checkpointing and retries
transient errors with exponential backoff.
"""

from __future__ import annotations

import asyncio
import time
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

logger = get_logger(__name__)


async def run_enumeration(connector_id: UUID) -> None:
    """
    Main enumeration loop:
    1. Load connector + credentials
    2. Resume from last checkpoint if any
    3. Iterate source files, publish each as a Kafka job
    4. Persist checkpoints periodically
    5. Clear checkpoint on successful completion
    """
    start_time = time.time()
    files_enumerated = 0
    settings = get_settings()

    session = await get_raw_session()

    try:
        # Load connector from DB
        result = await session.execute(select(Connector).where(Connector.id == connector_id))
        connector_model = result.scalar_one_or_none()

        if not connector_model:
            logger.error(f"Connector {connector_id} not found")
            return

        # Load credentials from Vault
        vault_service = VaultService()
        creds = vault_service.get_connector_secret(connector_model.secret_path)

        # Instantiate the source connector
        connector_instance = create_connector(connector_model, creds)

        # Create Kafka producer
        producer = create_producer(settings.kafka)

        # Load last checkpoint for resumption
        checkpoint_model = await load_checkpoint(session, connector_id)
        checkpoint_token = checkpoint_model.continuation_token if checkpoint_model else None

        logger.info(
            f"Starting enumeration for connector {connector_id}",
            extra={
                "connector_id": str(connector_id),
                "has_checkpoint": checkpoint_token is not None,
            },
        )

        max_retries = 5
        base_delay = 2

        async for job_descriptor, new_checkpoint_token in connector_instance.enumerate(checkpoint_token):
            retry_count = 0
            while True:
                try:
                    publish_job(producer, settings.kafka.ingestion_topic, job_descriptor)
                    files_enumerated += 1

                    METRICS.FILES_PROCESSED_TOTAL.labels(
                        source_type=job_descriptor.source_type, outcome="enumerated"
                    ).inc()

                    if new_checkpoint_token is not None:
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
        producer.flush()
        await clear_checkpoint(session, connector_id)
        await session.commit()

        duration = time.time() - start_time
        logger.info(
            f"Enumeration completed for connector {connector_id}",
            extra={
                "connector_id": str(connector_id),
                "files_enumerated": files_enumerated,
                "duration_seconds": f"{duration:.2f}",
            },
        )

    except PermanentConnectorError as e:
        logger.error(
            f"Permanent error during enumeration for connector {connector_id}: {e}",
            extra={"connector_id": str(connector_id)},
        )
    except Exception as e:
        logger.error(
            f"Unexpected error during enumeration for connector {connector_id}: {e}",
            extra={"connector_id": str(connector_id)},
        )
    finally:
        await session.close()

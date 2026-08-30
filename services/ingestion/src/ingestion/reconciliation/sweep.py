"""
Reconciliation sweep: compare enumerated source files against ingested
documents and re-drive any gaps to the ingestion-jobs topic.

Can be triggered via:
1. systemd timer (periodic)
2. Admin API endpoint
3. Manual script invocation
"""

from __future__ import annotations

import time
from typing import Optional
from uuid import UUID

from sqlalchemy import select

from ingestion.config import get_settings
from ingestion.services.database import get_raw_session
from ingestion.services.vault import VaultService
from ingestion.services.kafka import create_producer, publish_job
from ingestion.models.connector import Connector
from ingestion.models.document import Document
from ingestion.connectors import create_connector
from ingestion.monitoring.logging import get_logger
from ingestion.monitoring.metrics import METRICS

logger = get_logger(__name__)


async def run_reconciliation_sweep(connector_id: Optional[UUID] = None) -> None:
    """
    Re-enumerate all files from source(s) and compare against the documents table.
    Any file present in the source but not ingested is re-published to Kafka.
    """
    start_time = time.time()
    settings = get_settings()

    session = await get_raw_session()

    try:
        query = select(Connector)
        if connector_id:
            query = query.where(Connector.id == connector_id)

        result = await session.execute(query)
        connectors = result.scalars().all()

        vault_service = VaultService()
        producer = create_producer(settings.kafka)

        for connector_model in connectors:
            logger.info(
                f"Starting reconciliation sweep for connector {connector_model.id}",
                extra={"connector_id": str(connector_model.id)},
            )

            try:
                creds = vault_service.get_connector_secret(connector_model.secret_path)
                connector_instance = create_connector(connector_model, creds)
            except Exception as e:
                logger.error(
                    f"Failed to initialize connector {connector_model.id}: {e}",
                    extra={"connector_id": str(connector_model.id)},
                )
                continue

            # Enumerate all files from the source
            source_jobs: dict[str, object] = {}
            try:
                async for job_descriptor, _ in connector_instance.enumerate(None):
                    source_jobs[job_descriptor.source_ref] = job_descriptor
            except Exception as e:
                logger.error(
                    f"Failed to enumerate connector {connector_model.id}: {e}",
                    extra={"connector_id": str(connector_model.id)},
                )
                continue

            total_source = len(source_jobs)

            # Query all ingested source_refs for this connector
            doc_result = await session.execute(
                select(Document.source_ref).where(
                    Document.source_connector_id == connector_model.id
                )
            )
            ingested_refs = set(doc_result.scalars().all())
            total_ingested = len(ingested_refs)

            # Find gaps: files in source but not in DB
            gaps = set(source_jobs.keys()) - ingested_refs
            gaps_found = len(gaps)
            gaps_redriven = 0

            for source_ref in gaps:
                try:
                    publish_job(
                        producer, settings.kafka.ingestion_topic, source_jobs[source_ref]
                    )
                    gaps_redriven += 1
                except Exception as e:
                    logger.error(f"Failed to redrive job for {source_ref}: {e}")

            producer.flush()

            logger.info(
                f"Reconciliation report for connector {connector_model.id}",
                extra={
                    "connector_id": str(connector_model.id),
                    "total_source": total_source,
                    "total_ingested": total_ingested,
                    "gaps_found": gaps_found,
                    "gaps_redriven": gaps_redriven,
                },
            )

        duration = time.time() - start_time
        logger.info(
            f"Reconciliation sweep completed in {duration:.2f}s",
            extra={"duration_seconds": f"{duration:.2f}"},
        )

    except Exception as e:
        logger.error(f"Reconciliation sweep failed: {e}")
    finally:
        await session.close()

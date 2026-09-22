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
import asyncio
from uuid import UUID

from sqlalchemy import select

from ingestion.config import get_settings
from ingestion.connectors import create_connector
from ingestion.models.connector import Connector
from ingestion.models.document import SourceAsset
from ingestion.monitoring.logging import get_logger
from ingestion.services.database import get_raw_session
from ingestion.services.kafka import create_producer, publish_job
from ingestion.services.vault import VaultService
from ingestion.storage.source_metadata import is_metadata_control_file

logger = get_logger(__name__)


async def run_reconciliation_sweep(connector_id: UUID | None = None) -> None:
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
                connector_instance = await asyncio.to_thread(create_connector, connector_model, creds)
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
                    if is_metadata_control_file(job_descriptor, getattr(connector_instance, "metadata_mode", None)):
                        continue
                    source_jobs[job_descriptor.source_ref] = job_descriptor
            except Exception as e:
                logger.error(
                    f"Failed to enumerate connector {connector_model.id}: {e}",
                    extra={"connector_id": str(connector_model.id)},
                )
                continue

            total_source = len(source_jobs)

            # Query all catalogued physical source references for this connector.
            asset_result = await session.execute(
                select(SourceAsset).where(
                    SourceAsset.source_connector_id == connector_model.id,
                    SourceAsset.availability_status == "available",
                )
            )
            catalogued_assets = {asset.source_ref: asset for asset in asset_result.scalars().all()}
            total_ingested = len(catalogued_assets)

            # A missing location or changed listing fingerprint must be
            # re-hashed. This catches in-place S3/NAS replacements without a
            # redundant metadata request per unchanged object.
            gaps = set()
            for source_ref, job in source_jobs.items():
                asset = catalogued_assets.get(source_ref)
                if asset is None or asset.size_bytes != job.size_bytes or job.source_type == "S3" and job.etag and asset.etag != job.etag or (
                    job.source_type in {"NAS_SMB", "NAS_NFS"}
                    and job.mtime
                    and asset.source_last_modified_at != job.mtime
                ):
                    gaps.add(source_ref)
            gaps_found = len(gaps)
            gaps_redriven = 0

            for source_ref in gaps:
                try:
                    publish_job(producer, settings.kafka.ingestion_topic, source_jobs[source_ref])
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

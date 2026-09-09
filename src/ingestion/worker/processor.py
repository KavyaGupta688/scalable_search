from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from uuid import UUID

import uuid_utils
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from ingestion.connectors.base import SourceConnector, TransientConnectorError
from ingestion.models.document import Document, DuplicateLink
from ingestion.schemas.job import JobDescriptor, ProcessResult
from ingestion.schemas.metadata import DocumentMetadata
from ingestion.worker.validator import validate_mime_type, PermanentProcessingError, TransientProcessingError
from ingestion.worker.retry import classify_error
from ingestion.storage.minio_client import MinIOClient
from ingestion.storage.metadata_parser import extract_tika_metadata
from ingestion.storage.metadata_initializer import create_system_metadata
from ingestion.storage.metadata_normalizer import normalize_metadata
from ingestion.storage.event_publisher import publish_ai_processing_event
from ingestion.config import get_settings
from ingestion.monitoring.logging import get_logger
from ingestion.monitoring.metrics import METRICS
from ingestion.retention.entitlements import (
    assert_ingestion_allowed,
    find_entitlement,
    get_or_create_entitlement,
)
from ingestion.models.retention import LicenseEntitlement

logger = get_logger(__name__)

async def run_metadata_pipeline(
    target_key: str, 
    checksum: str, 
    mime_type: str, 
    total_bytes: int, 
    job: JobDescriptor, 
    minio_client: MinIOClient,
    session: AsyncSession,
    existing_entitlement: LicenseEntitlement | None,
    content: bytes | None = None,
    object_version_id: str | None = None,
) -> DocumentMetadata:
    tika_data = await extract_tika_metadata(target_key, minio_client, content=content)
    # The clock starts only after the final object exists and metadata
    # extraction has succeeded. If the surrounding DB transaction does not
    # commit, this timestamp never becomes an ingestion audit record.
    completed_at = datetime.now(timezone.utc)
    retention = get_settings().retention
    entitlement = existing_entitlement or await get_or_create_entitlement(
        session=session,
        checksum_sha256=checksum,
        completed_at=completed_at,
        policy_years=retention.policy_years,
    )
    effective_expiry_at = entitlement.expires_at
    if retention.enabled and retention.write_object_tags:
        await minio_client.put_retention_tags(
            target_key,
            {
                "ingested-at": completed_at.isoformat().replace("+00:00", "Z"),
                "expires-at": effective_expiry_at.isoformat().replace("+00:00", "Z"),
                "retention-policy": retention.lifecycle_rule_id,
            },
            version_id=object_version_id,
        )
    system_metadata = create_system_metadata(
        checksum=checksum,
        size_bytes=total_bytes,
        mime_type=mime_type,
        storage_path=target_key,
        job=job,
        entitlement_id=entitlement.id,
        bucket_name=minio_client.bucket,
        first_successful_ingested_at=completed_at,
        effective_expiry_at=effective_expiry_at,
        object_version_id=object_version_id,
    )
    return normalize_metadata(system_metadata, tika_data)

async def process_job(
    job: JobDescriptor, 
    connector: SourceConnector, 
    session: AsyncSession,
    minio_client: MinIOClient,
    producer=None
) -> ProcessResult:
    start_time = time.perf_counter()
    stage_seconds: dict[str, float] = {}

    def record_stage(stage: str, seconds: float) -> None:
        stage_seconds[stage] = stage_seconds.get(stage, 0.0) + seconds
        METRICS.PROCESSING_DURATION_SECONDS.labels(
            source_type=job.source_type, stage=stage
        ).observe(seconds)

    settings = get_settings()
    allowed_mimes = settings.allowed_mime_type_set
    target_key = job.target_storage_key()
    existing_entitlement: LicenseEntitlement | None = None
    
    try:
        exists_started = time.perf_counter()
        object_exists = await minio_client.object_exists(target_key)
        record_stage("minio_exists", time.perf_counter() - exists_started)
        if object_exists:
            # A destination object alone is not proof that ingestion completed:
            # the process could have crashed after MinIO completed but before
            # the PostgreSQL row was committed.  Only skip when both records
            # exist. End the read-only transaction before doing network I/O.
            database_started = time.perf_counter()
            existing_storage_doc = await session.scalar(
                select(Document).where(Document.storage_path == target_key)
            )
            record_stage("postgresql_read", time.perf_counter() - database_started)
            if existing_storage_doc is not None:
                logger.info(f"Object {target_key} already exists in storage. Skipping.")
                return ProcessResult.SKIPPED

            await session.rollback()
            logger.warning(
                "Destination object exists without a PostgreSQL document; reprocessing to repair metadata",
                extra={"job_id": job.provisional_id, "source_type": job.source_type},
            )
            
        use_single_put = (
            job.size_bytes is not None
            and job.size_bytes <= settings.worker.single_put_max_bytes
        )
        upload_id = None
        buffered_content = bytearray() if use_single_put else None
        if not use_single_put:
            minio_started = time.perf_counter()
            upload_id = await minio_client.create_multipart_upload(target_key)
            record_stage("minio_write", time.perf_counter() - minio_started)
        hasher = hashlib.sha256()
        
        parts = []
        total_bytes = 0
        mime_type = None
        
        try:
            part_number = 1
            source_stream = connector.open_stream(job).__aiter__()
            while True:
                read_started = time.perf_counter()
                try:
                    chunk = await source_stream.__anext__()
                except StopAsyncIteration:
                    record_stage("source_read", time.perf_counter() - read_started)
                    break
                record_stage("source_read", time.perf_counter() - read_started)

                if part_number == 1:
                    try:
                        validation_started = time.perf_counter()
                        mime_type = validate_mime_type(chunk, allowed_mimes)
                        record_stage("validation", time.perf_counter() - validation_started)
                    except PermanentProcessingError as e:
                        if upload_id is not None:
                            await minio_client.abort_multipart_upload(target_key, upload_id)
                        logger.warning(f"Job rejected due to MIME type: {e}")
                        return ProcessResult.REJECTED
                        
                hashing_started = time.perf_counter()
                hasher.update(chunk)
                record_stage("hashing", time.perf_counter() - hashing_started)
                if buffered_content is not None:
                    buffered_content.extend(chunk)
                    if len(buffered_content) > settings.worker.single_put_max_bytes:
                        raise PermanentProcessingError(
                            "Source object exceeded its enumerated size and the configured "
                            "single-put memory limit; re-enumerate this object"
                        )
                else:
                    minio_started = time.perf_counter()
                    etag = await minio_client.upload_part(
                        target_key, upload_id, part_number, chunk
                    )
                    record_stage("minio_write", time.perf_counter() - minio_started)
                    parts.append({"PartNumber": part_number, "ETag": etag})
                total_bytes += len(chunk)
                part_number += 1

            if mime_type is None:
                if upload_id is not None:
                    await minio_client.abort_multipart_upload(target_key, upload_id)
                logger.warning("Job rejected because the source object is empty")
                return ProcessResult.REJECTED
                
        except Exception as e:
            if upload_id is not None:
                await minio_client.abort_multipart_upload(target_key, upload_id)
            error_type = classify_error(e)
            if isinstance(e, TransientConnectorError) or error_type == 'transient':
                raise TransientProcessingError(f"Transient error during processing: {e}") from e
            else:
                raise PermanentProcessingError(f"Permanent error during processing: {e}") from e
                
        checksum = hasher.hexdigest()
        
        database_started = time.perf_counter()
        # Serialise only identical SHA-256 values.  Parallel workers can
        # freely process different objects, while concurrent copies of the
        # same content cannot both complete an object/INSERT race.  A hash
        # collision here merely serialises two unrelated writes; checksum
        # equality remains the actual duplicate decision.
        await session.execute(
            select(func.pg_advisory_xact_lock(func.hashtext(checksum)))
        )
        existing_entitlement = await find_entitlement(session, checksum)
        try:
            assert_ingestion_allowed(
                existing_entitlement, datetime.now(timezone.utc)
            )
        except PermanentProcessingError:
            if upload_id is not None:
                await minio_client.abort_multipart_upload(target_key, upload_id)
            raise
        stmt = select(Document).where(Document.checksum_sha256 == checksum)
        result = await session.execute(stmt)
        existing_doc = result.scalars().first()
        record_stage("postgresql_read", time.perf_counter() - database_started)
        
        if existing_doc:
            if upload_id is not None:
                await minio_client.abort_multipart_upload(target_key, upload_id)
            if existing_entitlement is None:
                raise PermanentProcessingError(
                    "Existing document has no checksum-based licence entitlement; "
                    "run migration 008 and repair the retention audit state"
                )
            duplicate = DuplicateLink(
                id=UUID(str(uuid_utils.uuid7())),
                original_document_id=existing_doc.id,
                source_connector_id=job.connector_id,
                source_ref=job.source_ref,
            )
            session.add(duplicate)
            database_started = time.perf_counter()
            await session.flush()
            record_stage("postgresql_write", time.perf_counter() - database_started)
            logger.info(f"Duplicate found for checksum {checksum}")
            return ProcessResult.DUPLICATE
            
        minio_started = time.perf_counter()
        if buffered_content is not None:
            object_version_id = await minio_client.put_object(
                target_key, bytes(buffered_content), mime_type
            )
        else:
            object_version_id = await minio_client.complete_multipart_upload(
                target_key, upload_id, parts
            )
        record_stage("minio_write", time.perf_counter() - minio_started)
        
        metadata_started = time.perf_counter()
        document_metadata = await run_metadata_pipeline(
            target_key,
            checksum,
            mime_type,
            total_bytes,
            job,
            minio_client,
            session,
            existing_entitlement,
            content=bytes(buffered_content) if buffered_content is not None else None,
            object_version_id=object_version_id,
        )
        record_stage("metadata", time.perf_counter() - metadata_started)
        
        doc = Document(**document_metadata.to_orm_dict())
        session.add(doc)
        database_started = time.perf_counter()
        await session.flush()
        record_stage("postgresql_write", time.perf_counter() - database_started)
        
        if producer:
            await publish_ai_processing_event(producer, document_metadata, settings.kafka)
            
        duration = time.perf_counter() - start_time
        record_stage("total", duration)
        METRICS.THROUGHPUT_BYTES_TOTAL.labels(source_type=job.source_type).inc(total_bytes)
            
        logger.info(
            f"Successfully processed job {job.provisional_id}",
            extra={
                "job_id": job.provisional_id,
                "source_type": job.source_type,
                "context": {
                    "bytes": total_bytes,
                    "run_id": str(job.run_id) if job.run_id else None,
                    "stage_seconds": {key: round(value, 6) for key, value in stage_seconds.items()},
                    "total_seconds": round(duration, 6),
                },
            },
        )
        return ProcessResult.SUCCESS
        
    except PermanentProcessingError:
        raise
    except Exception as e:
        if not isinstance(e, TransientProcessingError):
            e = TransientProcessingError(f"Unexpected error: {e}")
        raise e
    finally:
        # Failed, rejected, duplicate, and skipped jobs still contribute a
        # total latency sample.  Individual completed stages above identify
        # where time was actually spent.
        if "total" not in stage_seconds:
            record_stage("total", time.perf_counter() - start_time)

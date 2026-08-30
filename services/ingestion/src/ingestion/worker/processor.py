from __future__ import annotations

import hashlib
import time
from uuid import UUID

import uuid_utils
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ingestion.connectors.base import SourceConnector
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

logger = get_logger(__name__)

async def run_metadata_pipeline(
    target_key: str, 
    checksum: str, 
    mime_type: str, 
    total_bytes: int, 
    job: JobDescriptor, 
    minio_client: MinIOClient
) -> DocumentMetadata:
    tika_data = await extract_tika_metadata(target_key, minio_client)
    system_metadata = create_system_metadata(
        checksum=checksum,
        size_bytes=total_bytes,
        mime_type=mime_type,
        storage_path=target_key,
        job=job
    )
    return normalize_metadata(system_metadata, tika_data)

async def process_job(
    job: JobDescriptor, 
    connector: SourceConnector, 
    session: AsyncSession,
    minio_client: MinIOClient,
    producer=None
) -> ProcessResult:
    start_time = time.time()
    settings = get_settings()
    allowed_mimes = settings.allowed_mime_type_set
    target_key = job.target_storage_key()
    
    try:
        if await minio_client.object_exists(target_key):
            logger.info(f"Object {target_key} already exists in storage. Skipping.")
            return ProcessResult.SKIPPED
            
        upload_id = await minio_client.create_multipart_upload(target_key)
        hasher = hashlib.sha256()
        
        parts = []
        total_bytes = 0
        mime_type = None
        
        try:
            part_number = 1
            async for chunk in connector.open_stream(job):
                if part_number == 1:
                    try:
                        mime_type = validate_mime_type(chunk, allowed_mimes)
                    except PermanentProcessingError as e:
                        await minio_client.abort_multipart_upload(target_key, upload_id)
                        logger.warning(f"Job rejected due to MIME type: {e}")
                        return ProcessResult.REJECTED
                        
                hasher.update(chunk)
                etag = await minio_client.upload_part(target_key, upload_id, part_number, chunk)
                parts.append({"PartNumber": part_number, "ETag": etag})
                total_bytes += len(chunk)
                part_number += 1
                
        except Exception as e:
            await minio_client.abort_multipart_upload(target_key, upload_id)
            error_type = classify_error(e)
            if error_type == 'transient':
                raise TransientProcessingError(f"Transient error during processing: {e}") from e
            else:
                raise PermanentProcessingError(f"Permanent error during processing: {e}") from e
                
        checksum = hasher.hexdigest()
        
        stmt = select(Document).where(Document.checksum_sha256 == checksum)
        result = await session.execute(stmt)
        existing_doc = result.scalars().first()
        
        if existing_doc:
            await minio_client.abort_multipart_upload(target_key, upload_id)
            duplicate = DuplicateLink(
                id=uuid_utils.uuid7(),
                original_document_id=existing_doc.id,
                source_connector_id=job.connector_id,
                source_ref=job.source_ref,
            )
            session.add(duplicate)
            await session.flush()
            logger.info(f"Duplicate found for checksum {checksum}")
            return ProcessResult.DUPLICATE
            
        await minio_client.complete_multipart_upload(target_key, upload_id, parts)
        
        document_metadata = await run_metadata_pipeline(
            target_key, checksum, mime_type, total_bytes, job, minio_client
        )
        
        doc = Document(**document_metadata.to_orm_dict())
        session.add(doc)
        await session.flush()
        
        if producer:
            await publish_ai_processing_event(producer, document_metadata, settings.kafka)
            
        duration = time.time() - start_time
        if hasattr(METRICS, 'processing_duration_seconds'):
            METRICS.processing_duration_seconds.observe(duration)
        if hasattr(METRICS, 'files_processed_total'):
            METRICS.files_processed_total.inc()
        if hasattr(METRICS, 'throughput_bytes_total'):
            METRICS.throughput_bytes_total.inc(total_bytes)
            
        logger.info(f"Successfully processed job {job.id}")
        return ProcessResult.SUCCESS
        
    except PermanentProcessingError:
        raise
    except Exception as e:
        if not isinstance(e, TransientProcessingError):
            e = TransientProcessingError(f"Unexpected error: {e}")
        raise e

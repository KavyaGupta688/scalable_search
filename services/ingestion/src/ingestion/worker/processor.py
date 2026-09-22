"""Single-pass, zero-copy ingestion worker processing."""

from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime
from uuid import UUID

import uuid_utils
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.config import get_settings
from ingestion.connectors.base import SourceConnector, TransientConnectorError
from ingestion.models.document import Document, DocumentSourceMetadata, SourceAsset
from ingestion.models.retention import LicenseEntitlement
from ingestion.monitoring.logging import get_logger
from ingestion.monitoring.metrics import METRICS
from ingestion.retention.entitlements import find_entitlement, get_or_create_entitlement
from ingestion.schemas.job import JobDescriptor, ProcessResult, ProcessingStats
from ingestion.schemas.metadata import DocumentMetadata
from ingestion.schemas.source_metadata import StructuredSourceMetadata
from ingestion.storage.event_publisher import publish_ai_processing_event
from ingestion.storage.metadata_initializer import create_system_metadata
from ingestion.storage.source_metadata import is_metadata_control_file, resolve_source_metadata
from ingestion.worker.retry import classify_error
from ingestion.worker.validator import (
    PermanentProcessingError,
    TransientProcessingError,
    validate_mime_type,
)

logger = get_logger(__name__)


def _uuid7() -> UUID:
    return UUID(str(uuid_utils.uuid7()))


def _same_enumerated_source(asset: SourceAsset, job: JobDescriptor) -> bool:
    """Return True only when the listing fingerprint proves the source is unchanged."""

    if asset.size_bytes != job.size_bytes:
        return False
    if job.source_type == "S3" and job.etag:
        return asset.etag == job.etag and asset.source_version_id == job.version_id
    if job.source_type in {"NAS_SMB", "NAS_NFS"} and job.mtime:
        return asset.source_last_modified_at == job.mtime
    return False


async def run_metadata_pipeline(
    *,
    checksum: str,
    mime_type: str,
    total_bytes: int,
    job: JobDescriptor,
    source_asset_id: UUID,
    session: AsyncSession,
    existing_entitlement: LicenseEntitlement | None,
) -> DocumentMetadata:
    """Build system metadata; descriptive metadata is vendor-supplied separately."""

    completed_at = datetime.now(UTC)
    retention = get_settings().retention
    entitlement = existing_entitlement or await get_or_create_entitlement(
        session=session,
        checksum_sha256=checksum,
        completed_at=completed_at,
        policy_years=retention.policy_years,
    )
    system = create_system_metadata(
        checksum=checksum,
        size_bytes=total_bytes,
        mime_type=mime_type,
        job=job,
        entitlement_id=entitlement.id,
        source_asset_id=source_asset_id,
        first_successful_ingested_at=completed_at,
        effective_expiry_at=entitlement.expires_at,
    )
    values = system.model_dump()
    values["id"] = values.pop("document_id")
    return DocumentMetadata.model_validate(values)


async def _store_structured_metadata(
    session: AsyncSession,
    document_id: UUID,
    source_asset_id: UUID,
    metadata: StructuredSourceMetadata | None,
    *,
    overwrite: bool,
) -> None:
    if metadata is None:
        return
    row = await session.get(DocumentSourceMetadata, source_asset_id)
    values = metadata.to_orm_dict()
    if row is None:
        session.add(
            DocumentSourceMetadata(
                source_asset_id=source_asset_id,
                document_id=document_id,
                **values,
            )
        )
    elif overwrite:
        for key, value in values.items():
            setattr(row, key, value)


async def process_job(
    job: JobDescriptor,
    connector: SourceConnector,
    session: AsyncSession,
    producer=None,
    processing_stats: ProcessingStats | None = None,
) -> ProcessResult:
    """Catalogue one source object without copying it to destination storage."""

    started = time.perf_counter()
    processing_stats = processing_stats or ProcessingStats()
    stage_seconds = processing_stats.stage_seconds

    def record_stage(stage: str, seconds: float) -> None:
        stage_seconds[stage] = stage_seconds.get(stage, 0.0) + seconds
        METRICS.PROCESSING_DURATION_SECONDS.labels(source_type=job.source_type, stage=stage).observe(seconds)

    settings = get_settings()
    now = datetime.now(UTC)

    try:
        if is_metadata_control_file(job, getattr(connector, "metadata_mode", None)):
            logger.info(
                "Skipping vendor metadata control file as document content",
                extra={"job_id": job.provisional_id, "source_ref": job.source_ref},
            )
            return ProcessResult.SKIPPED

        metadata_started = time.perf_counter()
        structured_metadata = await resolve_source_metadata(connector, job)
        record_stage("source_metadata", time.perf_counter() - metadata_started)

        db_started = time.perf_counter()
        current_asset = await session.scalar(
            select(SourceAsset).where(
                SourceAsset.source_connector_id == job.connector_id,
                SourceAsset.source_ref == job.source_ref,
                SourceAsset.availability_status == "available",
            )
        )
        record_stage("postgresql_read", time.perf_counter() - db_started)
        if current_asset is not None and _same_enumerated_source(current_asset, job):
            processing_stats.document_id = current_asset.document_id
            processing_stats.source_asset_id = current_asset.id
            current_asset.last_verified_at = now
            await _store_structured_metadata(
                session,
                current_asset.document_id,
                current_asset.id,
                structured_metadata,
                overwrite=True,
            )
            logger.info(
                "Source location is unchanged; refreshed metadata without reading content",
                extra={"job_id": job.provisional_id, "source_ref": job.source_ref},
            )
            return ProcessResult.SKIPPED

        hasher = hashlib.sha256()
        total_bytes = 0
        mime_type: str | None = None
        try:
            source_stream = connector.open_stream(job).__aiter__()
            while True:
                read_started = time.perf_counter()
                try:
                    chunk = await source_stream.__anext__()
                except StopAsyncIteration:
                    record_stage("source_read", time.perf_counter() - read_started)
                    break
                record_stage("source_read", time.perf_counter() - read_started)
                if mime_type is None:
                    validation_started = time.perf_counter()
                    mime_type = validate_mime_type(chunk, settings.allowed_mime_type_set)
                    record_stage("validation", time.perf_counter() - validation_started)
                hashing_started = time.perf_counter()
                hasher.update(chunk)
                record_stage("hashing", time.perf_counter() - hashing_started)
                total_bytes += len(chunk)
                processing_stats.bytes_processed = total_bytes
        except PermanentProcessingError:
            raise
        except Exception as exc:
            error_type = classify_error(exc)
            if isinstance(exc, TransientConnectorError) or error_type == "transient":
                raise TransientProcessingError(f"Transient error while reading source: {exc}") from exc
            raise PermanentProcessingError(f"Permanent error while reading source: {exc}") from exc

        if mime_type is None:
            logger.warning("Job rejected because the source object is empty")
            return ProcessResult.REJECTED
        if job.size_bytes is not None and total_bytes != job.size_bytes:
            raise TransientProcessingError(
                "Source size changed between enumeration and processing; retry after re-enumeration"
            )

        checksum = hasher.hexdigest()
        db_started = time.perf_counter()
        await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(checksum))))
        locked_asset = await session.scalar(
            select(SourceAsset).where(
                SourceAsset.source_connector_id == job.connector_id,
                SourceAsset.source_ref == job.source_ref,
                SourceAsset.availability_status == "available",
            )
        )
        if locked_asset is not None and _same_enumerated_source(locked_asset, job):
            processing_stats.document_id = locked_asset.document_id
            processing_stats.source_asset_id = locked_asset.id
            locked_asset.last_verified_at = now
            await _store_structured_metadata(
                session,
                locked_asset.document_id,
                locked_asset.id,
                structured_metadata,
                overwrite=True,
            )
            return ProcessResult.SKIPPED
        if locked_asset is not None:
            current_asset = locked_asset
        existing_entitlement = await find_entitlement(session, checksum)
        existing_doc = await session.scalar(select(Document).where(Document.checksum_sha256 == checksum))
        record_stage("postgresql_read", time.perf_counter() - db_started)

        if current_asset is not None:
            current_asset.availability_status = "changed"
            current_asset.last_verified_at = now

        source_asset_id = _uuid7()
        if existing_doc is not None:
            processing_stats.document_id = existing_doc.id
            processing_stats.source_asset_id = source_asset_id
            session.add(
                SourceAsset(
                    id=source_asset_id,
                    document_id=existing_doc.id,
                    source_connector_id=job.connector_id,
                    source_ref=job.source_ref,
                    size_bytes=total_bytes,
                    etag=job.etag,
                    source_version_id=job.version_id,
                    source_last_modified_at=job.mtime,
                    availability_status="available",
                    last_verified_at=now,
                )
            )
            await _store_structured_metadata(
                session,
                existing_doc.id,
                source_asset_id,
                structured_metadata,
                overwrite=True,
            )
            write_started = time.perf_counter()
            await session.flush()
            record_stage("postgresql_write", time.perf_counter() - write_started)
            logger.info(
                "Duplicate content linked to an additional source location",
                extra={
                    "job_id": job.provisional_id,
                    "document_id": str(existing_doc.id),
                    "source_asset_id": str(source_asset_id),
                },
            )
            return ProcessResult.DUPLICATE

        document_metadata = await run_metadata_pipeline(
            checksum=checksum,
            mime_type=mime_type,
            total_bytes=total_bytes,
            job=job,
            source_asset_id=source_asset_id,
            session=session,
            existing_entitlement=existing_entitlement,
        )
        document = Document(**document_metadata.to_orm_dict())
        processing_stats.document_id = document.id
        processing_stats.source_asset_id = source_asset_id
        source_asset = SourceAsset(
            id=source_asset_id,
            document_id=document.id,
            source_connector_id=job.connector_id,
            source_ref=job.source_ref,
            size_bytes=total_bytes,
            etag=job.etag,
            source_version_id=job.version_id,
            source_last_modified_at=job.mtime,
            availability_status="available",
            last_verified_at=document_metadata.first_successful_ingested_at,
        )
        session.add_all([document, source_asset])
        await _store_structured_metadata(
            session,
            document.id,
            source_asset_id,
            structured_metadata,
            overwrite=True,
        )
        write_started = time.perf_counter()
        await session.flush()
        record_stage("postgresql_write", time.perf_counter() - write_started)

        await publish_ai_processing_event(
            producer,
            document_metadata,
            settings.kafka,
            structured_metadata=structured_metadata,
            run_id=job.run_id,
            session=session,
        )

        duration = time.perf_counter() - started
        record_stage("total", duration)
        METRICS.THROUGHPUT_BYTES_TOTAL.labels(source_type=job.source_type).inc(total_bytes)
        logger.info(
            "Successfully catalogued source content",
            extra={
                "job_id": job.provisional_id,
                "source_type": job.source_type,
                "context": {
                    "bytes": total_bytes,
                    "run_id": str(job.run_id) if job.run_id else None,
                    "document_id": str(document.id),
                    "source_asset_id": str(source_asset_id),
                    "stage_seconds": {key: round(value, 6) for key, value in stage_seconds.items()},
                    "total_seconds": round(duration, 6),
                },
            },
        )
        return ProcessResult.SUCCESS
    except PermanentProcessingError:
        raise
    except Exception as exc:
        if not isinstance(exc, TransientProcessingError):
            exc = TransientProcessingError(f"Unexpected error: {exc}")
        raise exc
    finally:
        if "total" not in stage_seconds:
            record_stage("total", time.perf_counter() - started)

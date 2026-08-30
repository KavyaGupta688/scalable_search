# api/routes.py
"""
FastAPI routes for the AI Tagging & Description Generation module.

These endpoints are the only public interface downstream modules
(Search & Indexing, Activity Logs) should use — they never query
this module's internals directly.
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, desc

from app.db import get_async_session
from app.models import EnrichmentTask, DocumentEnrichmentMetadata
from app.celery_app import process_validated_file
from app.event_schemas import ValidatedFileEvent


router = APIRouter()


@router.post("/enrich", status_code=202)
async def start_enrichment(event: ValidatedFileEvent) -> dict:
    """
    Accept a validated-file event from Ingestion and kick off the
    enrichment pipeline asynchronously via Celery.
    """
    task = process_validated_file.delay(
        event.file_id,
        event.storage_path,
        event.file_type,
        event.checksum,
        event.source_metadata,
    )
    return {
        "task_id": task.id,
        "file_id": event.file_id,
        "status": "queued",
    }


@router.get("/status/{file_id}")
async def get_status(file_id: str) -> dict:
    """Return the current enrichment task status and stage-by-stage results."""
    async with get_async_session() as session:
        result = await session.execute(
            select(EnrichmentTask).filter_by(file_id=file_id)
        )
        task_record = result.scalars().first()

    if not task_record:
        raise HTTPException(status_code=404, detail="Enrichment task not found")

    return {
        "file_id": file_id,
        "status": task_record.status,
        "current_stage": task_record.current_stage,
        "retry_count": task_record.retry_count,
        "stage_results": task_record.stage_results,
        "created_at": str(task_record.created_at) if task_record.created_at else None,
        "updated_at": str(task_record.updated_at) if task_record.updated_at else None,
    }


@router.get("/metadata/{file_id}")
async def get_metadata(file_id: str) -> dict:
    """Return the most recent generated metadata record for a file."""
    async with get_async_session() as session:
        result = await session.execute(
            select(DocumentEnrichmentMetadata)
            .filter_by(file_id=file_id)
            .order_by(desc(DocumentEnrichmentMetadata.created_at))
        )
        metadata_record = result.scalars().first()

    if not metadata_record:
        raise HTTPException(status_code=404, detail="Generated metadata not found")

    return {
        "id": metadata_record.id,
        "file_id": str(metadata_record.file_id),
        "model_version": metadata_record.model_version,
        "enrichment_version": metadata_record.enrichment_version,
        "generated_tags": metadata_record.generated_tags,
        "short_description": metadata_record.short_description,
        "long_description": metadata_record.long_description,
        "search_description": metadata_record.search_description,
        "accessibility_description": metadata_record.accessibility_description,
        "ocr_text": metadata_record.ocr_text,
        "transcribed_text": metadata_record.transcribed_text,
        "native_document_text": metadata_record.native_document_text,
        "privacy_safety_labels": metadata_record.privacy_safety_labels,
        "quality_labels": metadata_record.quality_labels,
        "confidence_scores": metadata_record.confidence_scores,
        "restricted_metadata": metadata_record.restricted_metadata,
        "model_versions": metadata_record.model_versions,
        "status": metadata_record.status,
        "created_at": str(metadata_record.created_at) if metadata_record.created_at else None,
    }


@router.post("/retry/{file_id}")
async def retry_task(file_id: str) -> dict:
    """
    Manually retry a failed_terminal or needs_review task.

    Resets the task status to queued and re-dispatches via Celery.
    The orchestrator will pick up from the first incomplete stage
    thanks to checkpointing.
    """
    async with get_async_session() as session:
        result = await session.execute(
            select(EnrichmentTask).filter_by(file_id=file_id)
        )
        task_record = result.scalars().first()

        if not task_record:
            raise HTTPException(status_code=404, detail="Enrichment task not found")

        if task_record.status not in ("failed_terminal", "needs_review"):
            raise HTTPException(
                status_code=400,
                detail=f"Task status is '{task_record.status}' — only failed_terminal and needs_review tasks can be retried",
            )

        task_record.status = "queued"
        task_record.retry_count = 0
        task_record.error_message = None
        await session.commit()

    # Re-dispatch — the orchestrator will read storage_path/file_type from the DB
    celery_task = process_validated_file.delay(
        file_id,
        task_record.storage_path or "",
        task_record.file_type or "",
        task_record.checksum or "",
    )

    return {
        "file_id": file_id,
        "status": "queued",
        "task_id": celery_task.id,
    }

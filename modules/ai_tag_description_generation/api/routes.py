# api/routes.py
"""
FastAPI routes for the AI Tagging & Description Generation module.

These endpoints are the only public interface downstream modules
(Search & Indexing, Activity Logs) should use — they never query
this module's internals directly.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from modules.shared.integration import internal_user
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select, desc
from uuid import UUID

from modules.ai_tag_description_generation.app.db import get_async_session
from modules.ai_tag_description_generation.app.models import (
    EnrichmentTask,
    DocumentEnrichmentMetadata,
)
from modules.ai_tag_description_generation.app.celery_app import process_validated_file
from modules.ai_tag_description_generation.app.event_schemas import EnrichmentRequest
from modules.ai_tag_description_generation.app.ingestion_client import (
    IngestionAccessError,
    get_document,
)


router = APIRouter(dependencies=[Depends(internal_user("ai", "ai:manage"))])


@router.get("/health/queue")
def queue_health() -> dict:
    """Verify the Redis connections used by Celery and event publication."""
    from modules.ai_tag_description_generation.app.redis_client import (
        check_redis_connections,
    )

    try:
        status = check_redis_connections()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Redis unavailable: {type(exc).__name__}",
        ) from exc

    if not status.healthy:
        raise HTTPException(
            status_code=503, detail="One or more Redis roles are unavailable"
        )
    return {
        "status": "ok",
        "broker": "connected",
        "result_backend": "connected",
        "events": "connected",
    }


@router.post("/enrich", status_code=202)
async def start_enrichment(request: EnrichmentRequest) -> dict:
    """
    Accept a validated-file event from Ingestion and kick off the
    enrichment pipeline asynchronously via Celery.
    """
    document_id = str(request.document_id)
    try:
        source = await run_in_threadpool(get_document, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IngestionAccessError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    async with get_async_session() as session:
        result = await session.execute(
            select(EnrichmentTask).filter_by(document_id=document_id)
        )
        task_record = result.scalars().first()
        if task_record is None:
            task_record = EnrichmentTask(
                document_id=document_id,
                status="queued",
                source_asset_id=source.source_asset_id,
                entitlement_id=source.entitlement_id,
                source_type=source.source_type,
                source_ref=source.source_ref,
                mime_type=source.mime_type,
                size_bytes=source.size_bytes,
                checksum_sha256=source.checksum_sha256,
                vendor_metadata=source.metadata,
            )
            session.add(task_record)
        elif task_record.status == "completed":
            return {"task_id": None, "document_id": document_id, "status": "completed"}
        else:
            task_record.status = "queued"
            task_record.error_message = None
        await session.commit()

    try:
        task = await run_in_threadpool(process_validated_file.delay, document_id)
    except Exception as exc:
        async with get_async_session() as session:
            result = await session.execute(
                select(EnrichmentTask).filter_by(document_id=document_id)
            )
            task_record = result.scalars().first()
            if task_record:
                task_record.status = "queue_failed"
                task_record.error_message = (
                    f"Queue dispatch failed: {type(exc).__name__}"
                )
                await session.commit()
        raise HTTPException(
            status_code=503, detail="Unable to queue enrichment task"
        ) from exc
    return {
        "task_id": task.id,
        "document_id": document_id,
        "status": "queued",
    }


@router.get("/status/{document_id}")
async def get_status(document_id: UUID) -> dict:
    """Return the current enrichment task status and stage-by-stage results."""
    document_id = str(document_id)
    async with get_async_session() as session:
        result = await session.execute(
            select(EnrichmentTask).filter_by(document_id=document_id)
        )
        task_record = result.scalars().first()

    if not task_record:
        raise HTTPException(status_code=404, detail="Enrichment task not found")

    return {
        "document_id": document_id,
        "status": task_record.status,
        "current_stage": task_record.current_stage,
        "retry_count": task_record.retry_count,
        "stage_results": task_record.stage_results,
        "created_at": str(task_record.created_at) if task_record.created_at else None,
        "updated_at": str(task_record.updated_at) if task_record.updated_at else None,
    }


@router.get("/metadata/{document_id}")
async def get_metadata(document_id: UUID) -> dict:
    """Return the most recent generated metadata record for a file."""
    async with get_async_session() as session:
        result = await session.execute(
            select(DocumentEnrichmentMetadata)
            .filter_by(document_id=document_id)
            .order_by(desc(DocumentEnrichmentMetadata.created_at))
        )
        metadata_record = result.scalars().first()

    if not metadata_record:
        raise HTTPException(status_code=404, detail="Generated metadata not found")

    return {
        "id": metadata_record.id,
        "document_id": str(metadata_record.document_id),
        "source_asset_id": str(metadata_record.source_asset_id)
        if metadata_record.source_asset_id
        else None,
        "run_id": str(metadata_record.run_id) if metadata_record.run_id else None,
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
        "created_at": str(metadata_record.created_at)
        if metadata_record.created_at
        else None,
    }


@router.post("/retry/{document_id}")
async def retry_task(document_id: UUID) -> dict:
    """
    Manually retry a failed_terminal or needs_review task.

    Resets the task status to queued and re-dispatches via Celery.
    The orchestrator will pick up from the first incomplete stage
    thanks to checkpointing.
    """
    document_id = str(document_id)
    async with get_async_session() as session:
        result = await session.execute(
            select(EnrichmentTask).filter_by(document_id=document_id)
        )
        task_record = result.scalars().first()

        if not task_record:
            raise HTTPException(status_code=404, detail="Enrichment task not found")

        if task_record.status not in (
            "failed_terminal",
            "needs_review",
            "partial",
            "queue_failed",
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Task status is '{task_record.status}' — only failed_terminal, "
                    "needs_review, partial, and queue_failed tasks can be retried"
                ),
            )

        task_record.status = "queued"
        task_record.retry_count = 0
        task_record.error_message = None
        await session.commit()

    # Re-dispatch; the worker refreshes metadata and entitlement through ingestion.
    try:
        celery_task = await run_in_threadpool(process_validated_file.delay, document_id)
    except Exception as exc:
        async with get_async_session() as session:
            result = await session.execute(
                select(EnrichmentTask).filter_by(document_id=document_id)
            )
            task_record = result.scalars().first()
            if task_record:
                task_record.status = "queue_failed"
                task_record.error_message = (
                    f"Queue dispatch failed: {type(exc).__name__}"
                )
                await session.commit()
        raise HTTPException(
            status_code=503, detail="Unable to queue enrichment retry"
        ) from exc

    return {
        "document_id": document_id,
        "status": "queued",
        "task_id": celery_task.id,
    }


@router.get("/tasks")
async def tasks(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    from sqlalchemy import func

    async with get_async_session() as session:
        total = await session.scalar(select(func.count()).select_from(EnrichmentTask))
        rows = (
            await session.scalars(
                select(EnrichmentTask)
                .order_by(EnrichmentTask.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return {
            "total": total,
            "tasks": [
                {
                    "document_id": r.document_id,
                    "status": r.status,
                    "stage": r.current_stage,
                    "error": r.error_message,
                    "updated_at": r.updated_at,
                    "mime_type": r.mime_type,
                    "run_id": r.run_id,
                }
                for r in rows
            ],
        }

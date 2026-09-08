# app/celery_app.py
"""
Layer 1 - Task Queue Configuration.

Configures Celery to process background enrichment jobs reliably.
Late acks prevent message loss on worker crash — the message stays in
Redis until the task is fully processed, not when the worker picks it up.
Prefetch multiplier = 1 because GPU tasks are heavy; pulling multiple
into a single worker just causes OOM or queue starvation.
"""

import logging
from celery import Celery
from modules.ai_tag_description_generation.app.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "ai_enrichment",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_acks_late=True,
    task_send_sent_event=True,
    worker_prefetch_multiplier=1,
    worker_send_task_events=True,
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        # RAM++, Whisper, and video jobs can take much longer than Celery's
        # Redis default. Redelivery is still safe because tasks are idempotent.
        "visibility_timeout": settings.CELERY_VISIBILITY_TIMEOUT,
        "socket_keepalive": True,
        "health_check_interval": 30,
    },
    result_backend_transport_options={
        "visibility_timeout": settings.CELERY_VISIBILITY_TIMEOUT,
        "health_check_interval": 30,
    },
    visibility_timeout=settings.CELERY_VISIBILITY_TIMEOUT,
    result_expires=settings.CELERY_RESULT_EXPIRES,
    # Don't let Celery auto-retry on its own — the orchestrator handles
    # retries internally with proper stage checkpointing.
    task_reject_on_worker_lost=True,
)


@celery_app.task(bind=True, name="ai_enrichment.process_validated_file", acks_late=True)
def process_validated_file(
    self,
    file_id: str,
):
    """
    Entry point for the AI enrichment pipeline, invoked via Celery.

    The orchestrator records stage status and partial results. This wrapper
    uses Celery retry for infrastructure-level failures such as temporarily
    unavailable PostgreSQL, MinIO, Redis, or model initialization.
    """
    try:
        from modules.ai_tag_description_generation.app.source_repository import get_source_document
        from modules.ai_tag_description_generation.app.storage_client import materialize_storage_path
        from modules.ai_tag_description_generation.worker.pipeline.orchestrator import run_enrichment_pipeline

        source = get_source_document(file_id)
        if source is None:
            raise ValueError(f"Document {file_id} was not found in the ingestion table")

        # Keep the downloaded MinIO object alive for the complete ML pipeline.
        # Only its temporary local path is sent to processors; PostgreSQL keeps
        # the durable object-storage path for retries and auditability.
        with materialize_storage_path(source.storage_path) as local_path:
            final_status = run_enrichment_pipeline(
                file_id=source.file_id,
                storage_path=source.storage_path,
                processing_path=local_path,
                file_type=source.file_type,
                checksum=source.checksum,
                source_metadata=source.source_metadata,
            )
        logger.info(f"[{file_id}] Pipeline completed with status: {final_status}")
        return {"file_id": file_id, "status": final_status}

    except Exception as exc:
        logger.error(f"[{file_id}] Unrecoverable pipeline failure: {exc}", exc_info=True)
        # Use Celery's retry with exponential backoff for truly
        # unexpected failures (DB connection lost, import error, etc.)
        countdown = settings.RETRY_BACKOFF_BASE ** self.request.retries
        raise self.retry(exc=exc, countdown=countdown, max_retries=settings.MAX_RETRIES)


if __name__ == "__main__":
    print(f"Celery app configured: broker={settings.CELERY_BROKER_URL}")

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
    document_id: str,
    event_payload: dict | None = None,
):
    """
    Entry point for the AI enrichment pipeline, invoked via Celery.

    The orchestrator records stage status and partial results. This wrapper
    uses Celery retry for infrastructure-level failures such as temporarily
    unavailable PostgreSQL, ingestion source access, Redis, or model initialization.
    """
    try:
        from modules.ai_tag_description_generation.app.event_schemas import IngestionDocumentEvent
        from modules.ai_tag_description_generation.app.ingestion_client import document_from_event, get_document

        document = (
            document_from_event(IngestionDocumentEvent.model_validate(event_payload))
            if event_payload
            else get_document(document_id)
        )
        final_status = process_ingestion_document(document)
        logger.info("[%s] Pipeline completed with status: %s", document_id, final_status)
        return {"document_id": document_id, "status": final_status}

    except Exception as exc:
        logger.error("[%s] Unrecoverable pipeline failure: %s", document_id, exc, exc_info=True)
        # Use Celery's retry with exponential backoff for truly
        # unexpected failures (DB connection lost, import error, etc.)
        if self.request.retries >= settings.MAX_RETRIES:
            try:
                from modules.ai_tag_description_generation.worker.pipeline.task_dispatcher import transition_status
                transition_status(document_id, "failed_terminal", error_message=str(exc))
            except Exception:
                logger.exception("[%s] Could not persist terminal failure", document_id)
            raise

        countdown = settings.RETRY_BACKOFF_BASE ** self.request.retries
        try:
            from modules.ai_tag_description_generation.worker.pipeline.task_dispatcher import increment_retry_count
            increment_retry_count(document_id)
        except Exception:
            logger.exception("[%s] Could not persist Celery retry count", document_id)
        raise self.retry(exc=exc, countdown=countdown, max_retries=settings.MAX_RETRIES)


def process_ingestion_document(document) -> str:
    """Process one validated ingestion snapshot; safe for Kafka redelivery."""
    from modules.ai_tag_description_generation.app.ingestion_client import materialize_document
    from modules.ai_tag_description_generation.worker.pipeline.orchestrator import run_enrichment_pipeline

    with materialize_document(document) as local_path:
        return run_enrichment_pipeline(document=document, processing_path=local_path)


@celery_app.task(bind=True, name="ai_enrichment.process_demo_file", acks_late=True)
def process_demo_file(self, file_path: str, dataset_category: str = "unknown"):
    """Process a local Kaggle sample through Celery without cloud storage/DBs."""
    from modules.ai_tag_description_generation.worker.pipeline.demo_pipeline import (
        run_ocr_demo_pipeline,
    )

    def report(stage: str, percent: int) -> None:
        self.update_state(
            state="PROGRESS",
            meta={"stage": stage, "percent": percent, "file": file_path},
        )

    logger.info("[demo:%s] Starting %s", self.request.id, file_path)
    result = run_ocr_demo_pipeline(file_path, dataset_category, progress=report)
    result["celery_task_id"] = self.request.id
    logger.info(
        "[demo:%s] Completed %s in %.2fs",
        self.request.id,
        file_path,
        result["duration_seconds"],
    )
    return result


if __name__ == "__main__":
    print(f"Celery app configured: broker={settings.CELERY_BROKER_URL}")

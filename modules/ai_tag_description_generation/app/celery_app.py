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
from app.config import settings

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
    worker_prefetch_multiplier=1,
    # Don't let Celery auto-retry on its own — the orchestrator handles
    # retries internally with proper stage checkpointing.
    task_reject_on_worker_lost=True,
)


@celery_app.task(bind=True, name="ai_enrichment.process_validated_file", acks_late=True)
def process_validated_file(
    self,
    file_id: str,
    storage_path: str,
    file_type: str,
    checksum: str,
    source_metadata: dict | None = None,
):
    """
    Entry point for the AI enrichment pipeline, invoked via Celery.

    The orchestrator handles all internal retries, checkpointing, and
    status transitions. This task wrapper only catches truly unexpected
    failures and uses Celery's retry for infrastructure-level issues
    (e.g. DB unreachable at startup).
    """
    try:
        from worker.pipeline.orchestrator import run_enrichment_pipeline

        final_status = run_enrichment_pipeline(
            file_id=file_id,
            storage_path=storage_path,
            file_type=file_type,
            checksum=checksum,
            source_metadata=source_metadata,
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

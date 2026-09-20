"""At-least-once ingestion event consumer for AI enrichment."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from pydantic import ValidationError

from modules.ai_tag_description_generation.app.config import settings
from modules.ai_tag_description_generation.app.event_schemas import (
    IngestionDocumentEvent,
)
from modules.ai_tag_description_generation.app.ingestion_client import (
    document_from_event,
)

logger = logging.getLogger(__name__)


def _kafka_security() -> dict[str, Any]:
    options: dict[str, Any] = {"security_protocol": settings.KAFKA_SECURITY_PROTOCOL}
    if settings.KAFKA_SASL_MECHANISM:
        options.update(
            sasl_mechanism=settings.KAFKA_SASL_MECHANISM,
            sasl_plain_username=settings.KAFKA_SASL_USERNAME,
            sasl_plain_password=settings.KAFKA_SASL_PASSWORD,
        )
    return options


def _event_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Kafka event value must be a JSON object")
    payload = value.get("payload", value)
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        raise ValueError("Kafka event payload must be a JSON object")
    return payload


def run() -> None:
    """Process one partition message at a time and commit only after DB success."""
    from kafka import KafkaConsumer, KafkaProducer
    from modules.ai_tag_description_generation.app.celery_app import (
        process_ingestion_document,
    )

    bootstrap_servers = [
        item.strip()
        for item in settings.KAFKA_BOOTSTRAP_SERVERS.split(",")
        if item.strip()
    ]
    consumer = KafkaConsumer(
        settings.KAFKA_AI_TOPIC,
        bootstrap_servers=bootstrap_servers,
        group_id=settings.KAFKA_AI_GROUP_ID,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        value_deserializer=lambda raw: raw,
        max_poll_records=1,
        max_poll_interval_ms=settings.KAFKA_MAX_POLL_INTERVAL_MS,
        session_timeout_ms=settings.KAFKA_SESSION_TIMEOUT_MS,
        heartbeat_interval_ms=settings.KAFKA_HEARTBEAT_INTERVAL_MS,
        **_kafka_security(),
    )
    producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda value: json.dumps(value, default=str).encode("utf-8"),
        **_kafka_security(),
    )

    logger.info(
        "Consuming %s as group %s",
        settings.KAFKA_AI_TOPIC,
        settings.KAFKA_AI_GROUP_ID,
    )
    processed = 0
    for message in consumer:
        try:
            raw_payload = _event_payload(json.loads(message.value.decode("utf-8")))
            event = IngestionDocumentEvent.model_validate(raw_payload)
        except (
            ValidationError,
            ValueError,
            TypeError,
            json.JSONDecodeError,
            UnicodeDecodeError,
        ) as exc:
            logger.error(
                "Rejecting invalid ingestion event at %s:%s: %s",
                message.partition,
                message.offset,
                exc,
            )
            producer.send(
                settings.KAFKA_AI_DLQ_TOPIC,
                {
                    "reason": "invalid_ingestion_event",
                    "source_topic": message.topic,
                    "source_partition": message.partition,
                    "source_offset": message.offset,
                    "error": str(exc),
                },
            ).get(timeout=30)
            consumer.commit()
            continue

        document = document_from_event(event)
        try:
            status = process_ingestion_document(document)
            if status == "skipped":
                # A live/unexpired processing lease is contention, not a model
                # failure. Redeliver this offset without consuming retries or
                # committing a later record past it.
                from kafka import TopicPartition
                consumer.seek(TopicPartition(message.topic, message.partition), message.offset)
                time.sleep(5)
                continue
            if status not in (
                "completed",
                "partial",
                "needs_review",
                "failed_terminal",
            ):
                raise RuntimeError("Document is locked by another worker")
        except Exception:
            from modules.ai_tag_description_generation.worker.pipeline.task_dispatcher import (
                increment_retry_count,
                transition_status,
            )
            from modules.ai_tag_description_generation.app.db import get_sync_session
            from modules.ai_tag_description_generation.app.models import EnrichmentTask

            increment_retry_count(document.document_id)
            with get_sync_session() as session:
                task = session.get(EnrichmentTask, document.document_id)
                exhausted = (
                    task is not None and task.retry_count >= settings.MAX_RETRIES
                )
            if exhausted:
                transition_status(
                    document.document_id,
                    "failed_terminal",
                    error_message="Kafka processing retry limit reached",
                )
                producer.send(
                    settings.KAFKA_AI_DLQ_TOPIC,
                    {
                        "reason": "processing_retry_exhausted",
                        "document_id": document.document_id,
                        "source_partition": message.partition,
                        "source_offset": message.offset,
                    },
                ).get(timeout=30)
                consumer.commit()
                continue
            logger.exception(
                "Processing failed for document %s; Kafka offset remains uncommitted",
                document.document_id,
            )
            raise

        # Model output is already durable. Broker acknowledgement failures must
        # not consume model retries or replace a successful task with a DLQ
        # failure. Restart/redelivery will reuse the persisted terminal result.
        consumer.commit()
        logger.info(
            "Committed ingestion event for document %s with AI status %s",
            document.document_id,
            status,
        )
        processed += 1
        if settings.AI_MAX_DOCUMENTS_PER_PROCESS > 0 and processed >= settings.AI_MAX_DOCUMENTS_PER_PROCESS:
            # Native model runtimes retain memory even after cache eviction.
            # The supervisor starts a fresh process only after durable output
            # and its Kafka acknowledgement; no offsets are skipped.
            logger.info("Recycling AI process after %s acknowledged documents", processed)
            consumer.close(autocommit=False)
            producer.close(timeout=10)
            return


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()

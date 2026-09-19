"""Retry durable delivery with row locks; a crash may replay but cannot lose work."""

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from modules.shared.delivery import Delivery
from modules.shared.integration import database_engine


def deliver(item):
    if item.kind == "ai-processing":
        from confluent_kafka import Producer

        producer = Producer(
            {
                "bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"],
                "acks": "all",
                "enable.idempotence": True,
            }
        )
        errors = []
        producer.produce(
            os.getenv("KAFKA_AI_TOPIC", "ai-processing-events"),
            key=item.payload["document_id"],
            value=json.dumps(item.payload),
            on_delivery=lambda err, msg: errors.append(err) if err else None,
        )
        if producer.flush(30) or errors:
            raise RuntimeError("Kafka delivery was not acknowledged")
    elif item.kind == "index":
        from modules.shared.indexer import index_document

        index_document(item.payload["document_id"])
        from modules.shared.audit import record

        record(
            "AI_INDEXED",
            "ai-worker",
            "document",
            item.payload["document_id"],
            event_id=item.key,
        )
    elif item.kind == "audit":
        from modules.shared.audit import record

        record(**item.payload)
    else:
        raise ValueError("Unknown delivery kind")


def drain(schema):
    with Session(database_engine(schema)) as session, session.begin():
        item = session.scalar(
            select(Delivery)
            .where(Delivery.delivered_at.is_(None))
            .order_by(Delivery.attempts, Delivery.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if item is None:
            return False
        item.attempts += 1
        try:
            deliver(item)
            item.delivered_at = datetime.now(timezone.utc)
            item.error = None
        except Exception as exc:
            item.error = type(exc).__name__
            logging.exception("Delivery failed: %s", item.key)
        return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "schema", choices=["ingestion", "enrichment", "search", "download"]
    )
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    while True:
        drain(args.schema)
        if args.once:
            return
        time.sleep(1)


if __name__ == "__main__":
    main()

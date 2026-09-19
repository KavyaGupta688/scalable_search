"""Real Kafka malformed-message/DLQ and protected AI materialization checks.

Requires the isolated stack with the RAM checkpoint intentionally absent.
"""

import json, time, uuid, dataclasses, tempfile
from pathlib import Path
from kafka import KafkaProducer, KafkaConsumer
from sqlalchemy import text
import httpx
from modules.shared.integration import database_engine
from modules.ai_tag_description_generation.app.ingestion_client import (
    get_document,
    materialize_document,
    SourceIntegrityError,
)

p = KafkaProducer(bootstrap_servers="kafka:9092")
position = p.send(
    "ai-processing-events", key=b"acceptance-invalid", value=b"\xffinvalid-json"
).get(timeout=20)
c = KafkaConsumer(
    "ai-processing-events-dlq",
    bootstrap_servers="kafka:9092",
    group_id="acceptance-dlq-" + uuid.uuid4().hex,
    auto_offset_reset="earliest",
    consumer_timeout_ms=90000,
)
found = False
for message in c:
    payload = json.loads(message.value)
    if (
        payload.get("reason") == "invalid_ingestion_event"
        and payload.get("source_offset") == position.offset
    ):
        found = True
        break
c.close()
assert found, "Malformed event was not observed in DLQ"
with database_engine("ingestion").connect() as db:
    did = str(
        db.execute(
            text(
                "SELECT d.id FROM documents d JOIN connectors c ON c.id=d.source_connector_id WHERE c.name LIKE 'acceptance-%' ORDER BY d.id DESC LIMIT 1"
            )
        ).scalar_one()
    )
for _ in range(90):
    with database_engine("enrichment").connect() as db:
        task = db.execute(
            text(
                "SELECT status,retry_count FROM enrichment_tasks WHERE document_id=:id"
            ),
            {"id": did},
        ).first()
    if task and task.status == "failed_terminal":
        break
    time.sleep(1)
assert task and task.status == "failed_terminal" and task.retry_count >= 3, task
r = httpx.get("http://ai:8000/ready", timeout=15)
assert r.status_code == 503 and r.json()["checks"]["ram_checkpoint"] is False
# Checksum mismatch must remove its temporary file even on failure.
doc = get_document(did)
before = set(Path(tempfile.gettempdir()).glob("ai-source-*"))
try:
    with materialize_document(dataclasses.replace(doc, checksum_sha256="0" * 64)):
        raise AssertionError("Wrong checksum was accepted")
except SourceIntegrityError:
    pass
assert set(Path(tempfile.gettempdir()).glob("ai-source-*")) == before
# Valid materialization uses real S3 via ingestion and cleans up on context exit.
with materialize_document(doc) as file:
    assert Path(file).stat().st_size == doc.size_bytes
    name = Path(file)
assert not name.exists()
print(
    "PASS: malformed Kafka event to DLQ, bounded missing-model retries/terminal state, readiness503, checksum rejection, real streamed AI source access and temporary-file cleanup"
)

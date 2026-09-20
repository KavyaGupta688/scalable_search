"""Regression cases discovered by the real multi-format S3 acceptance run."""
import json
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from PIL import Image

from modules.ai_tag_description_generation.app import kafka_consumer, celery_app
from modules.ai_tag_description_generation.worker.pipeline import task_dispatcher
from modules.ai_tag_description_generation.worker.pipeline.image_processor import process_image
from modules.ai_tag_description_generation.worker.pipeline.media_router import route_file, Modality
from modules.ai_tag_description_generation.worker.pipeline import orchestrator
from modules.ai_tag_description_generation.worker.pipeline.quality_safety import PrivacySafetyLabels
from modules.ai_tag_description_generation.worker.pipeline.retry_handler import DataQualityError
from modules.shared.publication import safety_cleared


def test_kafka_lock_contention_does_not_exhaust_retries_or_skip_offset(monkeypatch):
    import kafka
    did = str(uuid4())
    event = {key: str(uuid4()) for key in ('run_id', 'source_asset_id', 'source_connector_id', 'entitlement_id')}
    event.update(document_id=did, mime_type='image/gif', size_bytes=10,
                 checksum_sha256='a' * 64, source_ref='s3://test/a.gif', source_type='S3',
                 first_successful_ingested_at='2026-09-21T00:00:00Z', effective_expiry_at='2027-09-21T00:00:00Z')
    message = SimpleNamespace(value=json.dumps(event).encode(), topic='ai-processing-events', partition=0, offset=7)
    busy_attempts = kafka_consumer.settings.MAX_RETRIES + 2
    consumer = Mock()
    consumer.__iter__ = Mock(return_value=iter([message] * (busy_attempts + 1)))
    producer = Mock()
    process = Mock(side_effect=['skipped'] * busy_attempts + ['completed'])
    retries = Mock()
    monkeypatch.setattr(kafka, 'KafkaConsumer', Mock(return_value=consumer))
    monkeypatch.setattr(kafka, 'KafkaProducer', Mock(return_value=producer))
    monkeypatch.setattr(celery_app, 'process_ingestion_document', process)
    monkeypatch.setattr(task_dispatcher, 'increment_retry_count', retries)
    monkeypatch.setattr(kafka_consumer.time, 'sleep', Mock())
    kafka_consumer.run()
    assert consumer.seek.call_count == busy_attempts
    assert all(call.args[1] == 7 for call in consumer.seek.call_args_list)
    consumer.commit.assert_called_once_with()
    producer.send.assert_not_called()
    retries.assert_not_called()


def test_gif_routes_by_mime_and_extension_and_decodes(tmp_path):
    path = tmp_path / 'asset.gif'
    Image.new('RGB', (24, 16), 'red').save(path)
    assert route_file('extensionless', 'image/gif')[0] == Modality.IMAGE
    assert route_file(str(path))[0] == Modality.IMAGE
    image = process_image(str(path))
    assert image.original_size == (24, 16)
    assert image.frame_count == 1 and image.original_image.mode == 'RGB'


def test_broker_commit_failure_does_not_consume_model_retries(monkeypatch):
    import kafka
    from kafka.errors import CommitFailedError
    document = SimpleNamespace(document_id=str(uuid4()))
    message = SimpleNamespace(value=b'{}', topic='ai-processing-events', partition=0, offset=7)
    consumer = Mock()
    consumer.__iter__ = Mock(return_value=iter([message]))
    consumer.commit.side_effect = CommitFailedError('rebalanced after persistence')
    producer, retries, transition = Mock(), Mock(), Mock()
    monkeypatch.setattr(kafka, 'KafkaConsumer', Mock(return_value=consumer))
    monkeypatch.setattr(kafka, 'KafkaProducer', Mock(return_value=producer))
    monkeypatch.setattr(kafka_consumer.IngestionDocumentEvent, 'model_validate', Mock(return_value=object()))
    monkeypatch.setattr(kafka_consumer, 'document_from_event', Mock(return_value=document))
    monkeypatch.setattr(celery_app, 'process_ingestion_document', Mock(return_value='completed'))
    monkeypatch.setattr(task_dispatcher, 'increment_retry_count', retries)
    monkeypatch.setattr(task_dispatcher, 'transition_status', transition)
    with pytest.raises(CommitFailedError):
        kafka_consumer.run()
    retries.assert_not_called()
    transition.assert_not_called()
    producer.send.assert_not_called()


def test_low_memory_consumer_recycles_only_after_durable_acknowledgement(monkeypatch):
    import kafka
    document = SimpleNamespace(document_id=str(uuid4()))
    message = SimpleNamespace(value=b'{}', topic='ai-processing-events', partition=0, offset=7)
    consumer, producer = Mock(), Mock()
    consumer.__iter__ = Mock(return_value=iter([message, message]))
    steps=[]
    consumer.commit.side_effect=lambda:steps.append('acknowledged')
    consumer.close.side_effect=lambda **_:steps.append('closed')
    process=Mock(side_effect=lambda _:steps.append('persisted') or 'partial')
    monkeypatch.setattr(kafka, 'KafkaConsumer', Mock(return_value=consumer))
    monkeypatch.setattr(kafka, 'KafkaProducer', Mock(return_value=producer))
    monkeypatch.setattr(kafka_consumer.IngestionDocumentEvent, 'model_validate', Mock(return_value=object()))
    monkeypatch.setattr(kafka_consumer, 'document_from_event', Mock(return_value=document))
    monkeypatch.setattr(celery_app, 'process_ingestion_document', process)
    monkeypatch.setattr(kafka_consumer.settings, 'AI_MAX_DOCUMENTS_PER_PROCESS', 1)
    kafka_consumer.run()
    assert steps==['persisted','acknowledged','closed']
    assert process.call_count==1
    producer.close.assert_called_once_with(timeout=10)


def test_missing_preprocessing_cannot_claim_safety_clearance(monkeypatch):
    safety = Mock()
    monkeypatch.setattr(orchestrator.quality_safety, 'run_quality_safety_pipeline', safety)
    with pytest.raises(DataQualityError, match='safety cannot be assessed'):
        orchestrator._run_quality_safety('id', 'file', 'image/gif', {})
    safety.assert_not_called()


def test_animated_image_requires_review_if_only_first_frame_analyzed(tmp_path, monkeypatch):
    path = tmp_path / 'animated.gif'
    Image.new('RGB', (24, 16), 'red').save(path, save_all=True,
        append_images=[Image.new('RGB', (24, 16), 'blue')], duration=100, loop=0)
    image = process_image(str(path))
    assert image.frame_count == 2
    monkeypatch.setattr(orchestrator.quality_safety, 'run_quality_safety_pipeline',
                        lambda *_: (None, PrivacySafetyLabels()))
    ctx = {'modality': Modality.IMAGE, 'preprocessing_result': SimpleNamespace(data=image)}
    orchestrator._run_quality_safety('id', str(path), 'image/gif', ctx)
    assert ctx['safety_labels'].analysis_incomplete
    assert not safety_cleared(asdict(ctx['safety_labels']))

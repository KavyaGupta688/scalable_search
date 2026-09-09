from __future__ import annotations
import traceback
from typing import Optional, Any

from confluent_kafka import Producer, Consumer
from ingestion.schemas.job import JobDescriptor
from ingestion.monitoring.logging import get_logger

logger = get_logger(__name__)

def delivery_report(err, msg):
    """Callback for producer delivery reports."""
    if err is not None:
        logger.error(f"Message delivery failed: {err}")
    else:
        logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}]")

def create_producer(settings: Any) -> Producer:
    """Creates a configured Kafka producer."""
    conf = {
        'bootstrap.servers': settings.bootstrap_servers,
        'acks': 'all',
        'enable.idempotence': True,
        'retries': 5
    }
    if hasattr(settings, 'security_protocol') and settings.security_protocol:
        conf['security.protocol'] = settings.security_protocol
    
    return Producer(conf)

def create_consumer(settings: Any, group_id: Optional[str] = None) -> Consumer:
    """Creates a configured Kafka consumer."""
    conf = {
        'bootstrap.servers': settings.bootstrap_servers,
        'group.id': group_id or settings.group_id,
        'enable.auto.commit': False,
        'auto.offset.reset': settings.consumer_auto_offset_reset,
        'max.poll.interval.ms': settings.consumer_max_poll_interval_ms,
        'session.timeout.ms': settings.consumer_session_timeout_ms,
        'partition.assignment.strategy': 'cooperative-sticky'
    }
    return Consumer(conf)

def publish_job(producer: Producer, topic: str, job: JobDescriptor) -> None:
    """Serializes a job to JSON and publishes it to the specified topic."""
    try:
        producer.produce(
            topic,
            key=str(job.provisional_id).encode('utf-8'),
            value=job.model_dump_json().encode('utf-8'),
            callback=delivery_report
        )
        producer.poll(0)
    except Exception as e:
        logger.error(f"Failed to publish job {job.provisional_id}: {e}")
        raise

def publish_to_dead_letter(producer: Producer, topic: str, original_msg: Any, error: Exception) -> None:
    """Publishes a failed message to a dead letter topic with diagnostic headers."""
    try:
        headers = [
            ('error_message', str(error).encode('utf-8')),
            ('stacktrace', traceback.format_exc().encode('utf-8'))
        ]
        
        if original_msg is not None:
            if original_msg.topic():
                headers.append(('original_topic', original_msg.topic().encode('utf-8')))
            if original_msg.partition() is not None:
                headers.append(('original_partition', str(original_msg.partition()).encode('utf-8')))
            if original_msg.offset() is not None:
                headers.append(('original_offset', str(original_msg.offset()).encode('utf-8')))
            
            value = original_msg.value()
            key = original_msg.key()
        else:
            value = b''
            key = b''

        producer.produce(
            topic,
            key=key,
            value=value,
            headers=headers,
            callback=delivery_report
        )
        producer.poll(0)
    except Exception as e:
        logger.error(f"Failed to publish to dead letter queue: {e}")
        raise

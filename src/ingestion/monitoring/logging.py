from __future__ import annotations
import json
import logging
import queue
import socket
import traceback
from logging.handlers import DatagramHandler, QueueHandler, QueueListener, SocketHandler
from datetime import datetime, timezone
from typing import Any, Dict

from ingestion.config import get_settings

_logstash_listener: QueueListener | None = None


class JsonSocketHandler(SocketHandler):
    """Send newline-delimited formatted JSON instead of pickled LogRecords."""

    def makePickle(self, record: logging.LogRecord) -> bytes:  # noqa: N802
        return (self.format(record) + "\n").encode("utf-8")


class JsonDatagramHandler(DatagramHandler):
    """Send formatted JSON instead of the DatagramHandler pickle format."""

    def makePickle(self, record: logging.LogRecord) -> bytes:  # noqa: N802
        return (self.format(record) + "\n").encode("utf-8")

class StructuredJsonFormatter(logging.Formatter):
    """Custom formatter to output logs as structured JSON."""
    
    def __init__(self, service_name: str = "ingestion-module", environment: str = "dev"):
        super().__init__()
        self.service_name = service_name
        self.environment = environment
        self.hostname = socket.gethostname()
        
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "@timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "service": self.service_name,
            "environment": self.environment,
            "hostname": self.hostname,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "location": {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName
            }
        }
        
        # Include context dict for extra fields
        if hasattr(record, "context") and isinstance(record.context, dict):
            log_data["context"] = record.context
            
        # Extra fields commonly used
        for field in ["job_id", "run_id", "source_type", "object_key", "connector_id", "outcome"]:
            if hasattr(record, field):
                if "context" not in log_data:
                    log_data["context"] = {}
                log_data["context"][field] = getattr(record, field)

        # Exception info
        if record.exc_info:
            exc_type, exc_val, exc_tb = record.exc_info
            log_data["exception"] = {
                "type": exc_type.__name__ if exc_type else None,
                "message": str(exc_val),
                "stacktrace": "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
            }
            
        return json.dumps(log_data)

def setup_logging(settings: Any = None) -> None:
    """Configures the root logger with the structured JSON formatter."""
    global _logstash_listener
    if settings is None:
        try:
            settings = get_settings().logging
        except Exception:
            # Fallback if get_settings fails
            class DummySettings:
                level = "INFO"
                service_name = "ingestion-module"
                environment = "dev"
                logstash_host = None
                logstash_port = None
            settings = DummySettings()
            
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, getattr(settings, 'level', 'INFO').upper(), logging.INFO))
    
    # Remove existing handlers
    if _logstash_listener is not None:
        _logstash_listener.stop()
        _logstash_listener = None
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    formatter = StructuredJsonFormatter(
        service_name=getattr(settings, 'service_name', 'ingestion-module'),
        environment=getattr(settings, 'environment', 'dev')
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Logstash handler (optional)
    if hasattr(settings, 'logstash_host') and settings.logstash_host:
        try:
            port = getattr(settings, 'logstash_port', 5000)
            transport = getattr(settings, 'logstash_transport', 'tcp').lower()
            handler_class = JsonDatagramHandler if transport == 'udp' else JsonSocketHandler
            logstash_handler = handler_class(settings.logstash_host, port)
            logstash_handler.setFormatter(formatter)
            # Network logging must never stall ingestion. A bounded queue
            # isolates file processing from Logstash reconnect latency.
            log_queue: queue.Queue = queue.Queue(maxsize=10_000)
            root_logger.addHandler(QueueHandler(log_queue))
            _logstash_listener = QueueListener(
                log_queue, logstash_handler, respect_handler_level=True
            )
            _logstash_listener.start()
        except Exception as e:
            # Fall back to stdout only
            root_logger.warning(f"Could not setup Logstash handler: {e}")

def get_logger(name: str) -> logging.Logger:
    """Convenience function that returns a named logger."""
    return logging.getLogger(name)

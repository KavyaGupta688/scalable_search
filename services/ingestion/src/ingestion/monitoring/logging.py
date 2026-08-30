from __future__ import annotations
import json
import logging
import socket
import traceback
from datetime import datetime, timezone
from typing import Any, Dict

from ingestion.config import get_settings

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
        for field in ["job_id", "source_type", "object_key", "connector_id", "outcome"]:
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
            import logging.handlers
            port = getattr(settings, 'logstash_port', 5000)
            logstash_handler = logging.handlers.DatagramHandler(settings.logstash_host, port)
            logstash_handler.setFormatter(formatter)
            root_logger.addHandler(logstash_handler)
        except Exception as e:
            # Fall back to stdout only
            root_logger.warning(f"Could not setup Logstash handler: {e}")

def get_logger(name: str) -> logging.Logger:
    """Convenience function that returns a named logger."""
    return logging.getLogger(name)

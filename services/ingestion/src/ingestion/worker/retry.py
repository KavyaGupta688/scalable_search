from __future__ import annotations

import logging
from typing import Literal, Callable, Any
from tenacity import retry, retry_if_exception_type, wait_exponential, stop_after_attempt, before_sleep_log
from sqlalchemy.exc import OperationalError, IntegrityError
import botocore.exceptions

from ingestion.worker.validator import TransientProcessingError, PermanentProcessingError
from ingestion.monitoring.logging import get_logger

logger = get_logger(__name__)

def classify_error(exc: Exception) -> Literal['transient', 'permanent']:
    if isinstance(exc, botocore.exceptions.ClientError):
        code = exc.response.get('Error', {}).get('Code', 'Unknown')
        if code in ['RequestTimeout', 'SlowDown', 'InternalError', 'ServiceUnavailable', '500', '503']:
            return 'transient'
            
    if isinstance(exc, (botocore.exceptions.EndpointConnectionError, ConnectionError, TimeoutError)):
        return 'transient'
        
    if type(exc).__module__.startswith('smbprotocol.exceptions'):
        return 'transient'
        
    if isinstance(exc, OperationalError):
        return 'transient'
        
    if isinstance(exc, (PermanentProcessingError, ValueError, IntegrityError)):
        return 'permanent'
        
    return 'permanent'

def create_retry_decorator(max_attempts: int = 5) -> Callable[[Any], Any]:
    return retry(
        retry=retry_if_exception_type(TransientProcessingError),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        stop=stop_after_attempt(max_attempts),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )

from __future__ import annotations

import pybreaker
import logging
from ingestion.monitoring.metrics import METRICS
from ingestion.monitoring.logging import get_logger

logger = get_logger(__name__)

class CircuitBreakerOpenError(Exception):
    pass

class MetricsListener(pybreaker.CircuitBreakerListener):
    def state_change(self, cb, old_state, new_state):
        state_map = {
            pybreaker.STATE_CLOSED: 0,
            pybreaker.STATE_OPEN: 1,
            pybreaker.STATE_HALF_OPEN: 2
        }
        if hasattr(METRICS, 'circuit_breaker_state'):
            METRICS.circuit_breaker_state.labels(name=cb.name).set(state_map.get(new_state.name, 0))
        logger.info(f"Circuit breaker {cb.name} transitioned from {old_state.name} to {new_state.name}")

class MinIOCircuitBreaker:
    def __init__(self, fail_max: int = None, reset_timeout: int = None, name: str = "minio"):
        from ingestion.config import get_settings
        settings = get_settings().worker
        self.breaker = pybreaker.CircuitBreaker(
            fail_max=fail_max or settings.circuit_breaker_fail_max,
            reset_timeout=reset_timeout or settings.circuit_breaker_reset_timeout_seconds,
            name=name,
            listeners=[MetricsListener()]
        )
        self.name = name

    @property
    def is_open(self) -> bool:
        return self.breaker.current_state == pybreaker.STATE_OPEN
        
    def call(self, func, *args, **kwargs):
        try:
            return self.breaker.call(func, *args, **kwargs)
        except pybreaker.CircuitBreakerError as e:
            raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is open") from e

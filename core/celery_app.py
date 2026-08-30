"""
Celery Application Configuration for Asynchronous S3 Downloads & Watermarking.
Uses Redis as both Message Broker and Result Backend.
"""
import sys
from pathlib import Path
try:
    from celery import Celery
    HAS_CELERY = True
except ImportError:
    HAS_CELERY = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

if HAS_CELERY:
    celery_app = Celery(
        "watermark_gateway_worker",
        broker=CELERY_BROKER_URL,
        backend=CELERY_RESULT_BACKEND,
        include=["core.tasks"]
    )
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=3600,  # 1 hour limit for multi-GB batches
        worker_prefetch_multiplier=1,
        result_expires=86400,  # Retain task results in Redis for 24 hours
    )
else:
    class DummyCelery:
        def __init__(self):
            self.conf = {}
        def task(self, *args, **kwargs):
            def decorator(func):
                func.delay = lambda *a, **k: func(*a, **k)
                return func
            return decorator
    celery_app = DummyCelery()

if __name__ == "__main__":
    if HAS_CELERY:
        celery_app.start()
    else:
        print("Celery is not installed in this Python environment.")

"""Dedicated download queue. PostgreSQL jobs remain the durable source of truth."""
import os
import sys
from pathlib import Path
from celery import Celery

sys.path.insert(0, str(Path(__file__).resolve().parent))

app = Celery("integrated_download", broker=os.environ["REDIS_URL"])
app.conf.update(
    task_default_queue="downloads", task_ignore_result=True,
    task_acks_late=True, task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1, broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 21600},
    beat_schedule={"recover-committed-downloads": {"task": "downloads.recover", "schedule": 5.0}},
)


@app.task(name="downloads.package")
def package(job_id):
    from integrated import work_once
    return work_once(job_id)


@app.task(name="downloads.recover")
def recover():
    # Includes jobs whose initial broker publish failed. Row locks prevent
    # concurrent Celery/direct executions from packaging the same job twice.
    from integrated import work_once, cleanup_packages
    work_once()
    cleanup_packages()

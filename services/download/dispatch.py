"""Bounded API-process fast lane, with Redis admission and durable queue recovery."""
import logging
import os
from sqlalchemy import text, bindparam
from modules.shared.integration import database_engine

log = logging.getLogger(__name__)


def fast_candidate(ids):
    if len(ids) > 2:
        return False
    from core.injectors.dispatcher import signal_method
    query = text("SELECT file_size,file_name FROM search.file_metadata WHERE file_id IN :ids").bindparams(bindparam("ids", expanding=True))
    with database_engine("search").connect() as conn:
        rows = conn.execute(query, {"ids": ids}).all()
    return (len(rows) == len(ids) and all(r.file_size is not None for r in rows)
            and sum(r.file_size for r in rows) <= int(os.getenv("DOWNLOAD_DIRECT_MAX_BYTES", "2097152"))
            and not any(signal_method(r.file_name or "") for r in rows))


def dispatch(job_id, ids, background):
    from redis import Redis
    lease = None
    try:
        if fast_candidate(ids):
            client = Redis.from_url(os.environ["REDIS_URL"], socket_connect_timeout=1, socket_timeout=1)
            lease = client.lock("download:direct-slot", timeout=300, blocking=False, thread_local=False)
            if lease.acquire(blocking=False):
                background.add_task(direct, job_id, lease)
                return
    except Exception:
        log.warning("Download fast lane unavailable; committed job remains queued")
    try:
        from integrated_celery import package
        package.apply_async(args=[job_id], retry=False)
    except Exception:
        log.warning("Download broker unavailable; recovery will pick up committed job %s", job_id)


def direct(job_id, lease):
    try:
        from integrated import work_once
        work_once(job_id, mode="direct")
    finally:
        try:
            lease.release()
        except Exception:
            log.warning("Download fast-lane lease expired or Redis became unavailable")

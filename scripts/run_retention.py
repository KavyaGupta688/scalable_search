#!/usr/bin/env python3
"""Install MinIO lifecycle policy and continuously reconcile retention audit state."""

from __future__ import annotations

import argparse
import asyncio

from prometheus_client import start_http_server

from ingestion.config import get_settings
from ingestion.monitoring.logging import get_logger, setup_logging
from ingestion.monitoring.metrics import METRICS
from ingestion.retention.service import install_lifecycle_policy, reconcile_retention_once
from ingestion.storage.minio_client import MinIOClient


async def run(*, once: bool, apply_only: bool) -> None:
    settings = get_settings()
    logger = get_logger("retention")
    minio = MinIOClient()

    while True:
        try:
            await install_lifecycle_policy(minio, settings.retention)
            if not apply_only:
                await reconcile_retention_once(minio=minio, retention=settings.retention)
        except Exception:
            logger.exception("Retention cycle failed; it will be retried")
            if once or apply_only:
                raise

        if once or apply_only:
            return
        await asyncio.sleep(settings.retention.reconciliation_interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run one lifecycle/reconciliation cycle")
    parser.add_argument("--apply-only", action="store_true", help="Only install/verify lifecycle rules")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(settings.logging)
    METRICS.RETENTION_ENFORCEMENT_ENABLED.set(1 if settings.retention.enabled else 0)
    if settings.retention.metrics_port:
        start_http_server(settings.retention.metrics_port)
    asyncio.run(run(once=args.once, apply_only=args.apply_only))


if __name__ == "__main__":
    main()

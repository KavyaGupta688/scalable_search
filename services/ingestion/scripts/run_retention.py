#!/usr/bin/env python3
"""Continuously reconcile licence-expiry audit state."""

from __future__ import annotations

import argparse
import asyncio

from prometheus_client import start_http_server

from ingestion.config import get_settings
from ingestion.monitoring.logging import get_logger, setup_logging
from ingestion.monitoring.metrics import METRICS
from ingestion.retention.service import reconcile_retention_once


async def run(*, once: bool) -> None:
    settings = get_settings()
    logger = get_logger("retention")
    while True:
        try:
            await reconcile_retention_once(retention=settings.retention)
        except Exception:
            logger.exception("Retention cycle failed; it will be retried")
            if once:
                raise

        if once:
            return
        await asyncio.sleep(settings.retention.reconciliation_interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run one expiry reconciliation cycle")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(settings.logging)
    METRICS.RETENTION_ENFORCEMENT_ENABLED.set(1 if settings.retention.enabled else 0)
    if settings.retention.metrics_port:
        start_http_server(settings.retention.metrics_port)
    asyncio.run(run(once=args.once))


if __name__ == "__main__":
    main()

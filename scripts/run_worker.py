#!/usr/bin/env python3
"""Entrypoint for the Data Ingestion Worker (Kafka consumer)."""
import asyncio
import signal
from prometheus_client import start_http_server
from ingestion.config import get_settings
from ingestion.monitoring.logging import setup_logging, get_logger
from ingestion.worker.consumer import run_consumer

def main():
    settings = get_settings()
    setup_logging(settings.logging)
    logger = get_logger("worker")
    if settings.worker.metrics_port:
        start_http_server(settings.worker.metrics_port)
        logger.info(
            "Worker metrics endpoint started",
            extra={"context": {"metrics_port": settings.worker.metrics_port}},
        )
    logger.info("Starting ingestion worker...")
    
    loop = asyncio.new_event_loop()
    # Handle SIGTERM/SIGINT for graceful shutdown
    install_signal_handlers(loop, logger)
    
    try:
        loop.run_until_complete(run_consumer())
    finally:
        loop.close()

async def shutdown(loop, logger):
    logger.info("Received shutdown signal, stopping worker...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()


def install_signal_handlers(loop, logger):
    """Install graceful shutdown handlers on Unix and native Windows Python."""
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(
                sig,
                lambda: asyncio.ensure_future(shutdown(loop, logger), loop=loop),
            )
        except NotImplementedError:
            # ProactorEventLoop on Windows does not implement add_signal_handler.
            signal.signal(
                sig,
                lambda *_args: loop.call_soon_threadsafe(
                    lambda: asyncio.ensure_future(shutdown(loop, logger), loop=loop)
                ),
            )

if __name__ == "__main__":
    main()

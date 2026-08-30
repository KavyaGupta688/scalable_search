#!/usr/bin/env python3
"""Entrypoint for the Data Ingestion Worker (Kafka consumer)."""
import asyncio
import signal
from ingestion.config import get_settings
from ingestion.monitoring.logging import setup_logging, get_logger
from ingestion.worker.consumer import run_consumer

def main():
    settings = get_settings()
    setup_logging(settings.logging)
    logger = get_logger("worker")
    logger.info("Starting ingestion worker...")
    
    loop = asyncio.new_event_loop()
    # Handle SIGTERM/SIGINT for graceful shutdown
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.ensure_future(shutdown(loop, logger)))
    
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

if __name__ == "__main__":
    main()

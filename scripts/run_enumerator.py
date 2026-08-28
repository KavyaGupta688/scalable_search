#!/usr/bin/env python3
"""Entrypoint for the Data Ingestion Enumerator."""
import asyncio
import sys
from ingestion.config import get_settings
from ingestion.monitoring.logging import setup_logging, get_logger
from ingestion.orchestration.enumerator import run_enumeration
from uuid import UUID

def main():
    settings = get_settings()
    setup_logging(settings.logging)
    logger = get_logger("enumerator")
    
    if len(sys.argv) < 2:
        logger.error("Usage: run_enumerator.py <connector_id>")
        sys.exit(1)
    
    connector_id = UUID(sys.argv[1])
    logger.info(f"Starting enumeration for connector {connector_id}")
    asyncio.run(run_enumeration(connector_id))

if __name__ == "__main__":
    main()

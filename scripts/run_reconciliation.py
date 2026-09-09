#!/usr/bin/env python3
"""Entrypoint for the Reconciliation Sweep."""
import asyncio
import sys
from ingestion.config import get_settings
from ingestion.monitoring.logging import setup_logging, get_logger
from ingestion.reconciliation.sweep import run_reconciliation_sweep
from uuid import UUID

def main():
    settings = get_settings()
    setup_logging(settings.logging)
    logger = get_logger("reconciliation")
    
    connector_id = UUID(sys.argv[1]) if len(sys.argv) > 1 else None
    logger.info(f"Starting reconciliation sweep (connector={connector_id or 'all'})")
    asyncio.run(run_reconciliation_sweep(connector_id))

if __name__ == "__main__":
    main()

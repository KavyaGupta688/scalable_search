#!/usr/bin/env python3
"""Entrypoint for the Data Ingestion API server."""
import uvicorn
from ingestion.config import get_settings
from ingestion.monitoring.logging import setup_logging

def main():
    settings = get_settings()
    setup_logging(settings.logging)
    uvicorn.run(
        "ingestion.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        log_level=settings.logging.level.lower(),
        reload=not settings.is_production,
    )

if __name__ == "__main__":
    main()

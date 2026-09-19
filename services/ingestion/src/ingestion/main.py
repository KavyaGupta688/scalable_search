from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ingestion.config import get_settings
from ingestion.monitoring.logging import get_logger
from ingestion.api.router_connectors import router as connectors_router
from ingestion.api.router_documents import router as documents_router
from ingestion.api.router_ingestion import router as ingestion_router
from ingestion.api.router_auth import router as auth_router
from ingestion.api.router_health import router as health_router

logger = get_logger(__name__)

def create_app() -> FastAPI:
    settings = get_settings()
    
    app = FastAPI(
        title="Data Ingestion API",
        description="API for managing data connectors and ingestion pipelines",
        version="1.0.0"
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.include_router(connectors_router)
    app.include_router(documents_router)
    app.include_router(ingestion_router)
    app.include_router(auth_router)
    app.include_router(health_router)
    
    @app.on_event("startup")
    async def startup_event():
        logger.info("Application starting up")
        
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Application shutting down")
        
    return app

app = create_app()

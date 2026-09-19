import os
from fastapi import FastAPI, Depends
from modules.shared.integration import internal_user
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import logging
from app.core.config import get_settings
from app.core.exceptions import MultimodalSearchException, multimodal_exception_handler
from app.db.postgres import init_db
from app.db.qdrant import init_qdrant
from app.api.router import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("multimodal_search")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Multimodal Search backend services...")
    from sqlalchemy import text
    from app.db.postgres import engine

    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1 FROM file_metadata LIMIT 1"))
    init_qdrant()
    logger.info("Multimodal Search Module ready for traffic.")
    yield
    logger.info("Shutting down Multimodal Search backend.")


app = FastAPI(
    title=settings.APP_NAME,
    description="Multimodal Search API for discovery, hybrid keyword/semantic search, faceted filtering, and audit integration.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
app.add_exception_handler(MultimodalSearchException, multimodal_exception_handler)

# Include API Router
app.include_router(
    api_router, dependencies=[Depends(internal_user("search", "search:read"))]
)

frontend_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "qdrant_embedded": settings.QDRANT_EMBEDDED,
        "redis_fallback": settings.REDIS_FALLBACK_MEMORY,
    }


@app.get("/ready")
def readiness_check():
    from modules.shared.readiness import readiness

    return readiness("search", vectors=True)

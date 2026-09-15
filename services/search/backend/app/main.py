import os
from fastapi import FastAPI
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
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("multimodal_search")
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Multimodal Search backend services...")
    await init_db()
    init_qdrant()
    logger.info("Multimodal Search Module ready for traffic.")
    yield
    logger.info("Shutting down Multimodal Search backend.")

app = FastAPI(
    title=settings.APP_NAME,
    description="Multimodal Search API for discovery, hybrid keyword/semantic search, faceted filtering, and audit integration.",
    version="1.0.0",
    lifespan=lifespan
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
app.include_router(api_router)

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "qdrant_embedded": settings.QDRANT_EMBEDDED,
        "redis_fallback": settings.REDIS_FALLBACK_MEMORY
    }

@app.get("/style.css", include_in_schema=False)
async def get_style_css():
    css_path = os.path.join(frontend_dir, "style.css")
    if os.path.exists(css_path):
        return FileResponse(css_path, media_type="text/css")
    return {"error": "style.css not found"}

@app.get("/app.js", include_in_schema=False)
async def get_app_js():
    js_path = os.path.join(frontend_dir, "app.js")
    if os.path.exists(js_path):
        return FileResponse(js_path, media_type="application/javascript")
    return {"error": "app.js not found"}

@app.get("/", tags=["Root"])
async def root():
    index_file = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file, media_type="text/html")
    return {
        "message": "Welcome to Samsung Multimodal Search & Discovery API",
        "docs_url": "/docs",
        "ui_url": "/ui"
    }

if os.path.exists(frontend_dir):
    app.mount("/ui", StaticFiles(directory=frontend_dir, html=True), name="ui")

import os
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager
import logging
from sqlalchemy import text
from app.core.config import get_settings
from app.core.exceptions import MultimodalSearchException, multimodal_exception_handler
from app.db.postgres import init_db, engine
from app.db.qdrant import init_qdrant, get_qdrant_client
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
    logger.info(f"Initializing Multimodal Search backend services (APP_ENV={settings.APP_ENV})...")
    # Intentionally not wrapped in try/except: a bad Postgres or Qdrant
    # connection in production must stop the app from starting, not let it
    # come up "healthy" and fail every search request instead.
    await init_db()
    init_qdrant()
    logger.info("Multimodal Search Module ready for traffic.")
    yield
    logger.info("Shutting down Multimodal Search backend.")
    await engine.dispose()

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

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "multimodal-search-frontend"))

@app.get("/health", tags=["Health"])
@app.get("/livez", tags=["Health"], include_in_schema=False)
async def health_check():
    """
    Liveness only: the process is up and serving HTTP. Does not check
    downstream dependencies - use /readyz for that (see monitoring §11).
    """
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "qdrant_embedded": settings.QDRANT_EMBEDDED,
        "redis_fallback": settings.REDIS_FALLBACK_MEMORY
    }

@app.get("/readyz", tags=["Health"])
async def readiness_check():
    """
    Readiness: actually pings Postgres and Qdrant so a load balancer/k8s can
    take an instance out of rotation the moment a dependency is unreachable,
    instead of routing traffic to an instance that will 503 every search.
    """
    checks: dict[str, str] = {}
    healthy = True

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres" if settings.is_postgres else "database"] = "ok"
    except Exception as e:
        healthy = False
        checks["database"] = f"unavailable: {e}"

    try:
        await asyncio.to_thread(get_qdrant_client().get_collections)
        checks["qdrant"] = "ok"
    except Exception as e:
        healthy = False
        checks["qdrant"] = f"unavailable: {e}"

    status_code = 200 if healthy else 503
    return JSONResponse(status_code=status_code, content={"status": "ready" if healthy else "not_ready", "checks": checks})

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

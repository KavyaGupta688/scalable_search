"""

FastAPI Server Entrypoint for the Watermarking Gateway.
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import BASE_DIR, SERVER_HOST, SERVER_PORT
from api.routes import router as api_router

app = FastAPI(
    title="AI Data Platform - Download & Metadata Watermarking Gateway",
    description="S3 gateway with metadata tracking, optional experimental signal/native-codec watermarks, and authenticated download-ID inspection.",
    version="2.0.0"
)

# Enable CORS for cross-origin integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(api_router, prefix="/api")

# Mount Web Dashboard Frontend
frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

if __name__ == "__main__":
    print(f">> Starting Watermarking Gateway on http://{SERVER_HOST}:{SERVER_PORT}")
    uvicorn.run("api.server:app", host=SERVER_HOST, port=SERVER_PORT, reload=False)

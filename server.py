import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from modules.ai_tag_description_generation.api.routes import router as ai_router
from modules.download_auditing.api.routes import router as download_router
from modules.ingestion.api.routes import router as ingestion_router
from modules.searching.api.routes import router as search_router
from modules.shared.auth.routes import router as auth_router

app = FastAPI(title="Nexus Platform API", version="0.2.0")

# ── CORS (allow frontend dev server) ───────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────────────
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(search_router, prefix="/search", tags=["search"])
app.include_router(ingestion_router, prefix="/ingestion", tags=["ingestion"])
app.include_router(ai_router, prefix="/ai", tags=["ai-enrichment"])
app.include_router(download_router, prefix="/downloads", tags=["downloads"])


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


def run() -> None:
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)


dist_dir = "frontend/dist" if os.path.exists("frontend/dist") else "frontend"
app.mount("/", StaticFiles(directory=dist_dir, html=True), name="frontend")

if __name__ == "__main__":
    run()
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from modules.ai_tag_description_generation.api.routes import router as ai_router
from modules.download_auditing.api.routes import router as download_router
from modules.ingestion.api.routes import router as ingestion_router
from modules.searching.api.routes import router as search_router

app = FastAPI(title="SMSPRSM Platform API", version="0.1.0")
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


import os

dist_dir = "frontend/dist" if os.path.exists("frontend/dist") else "frontend"
app.mount("/", StaticFiles(directory=dist_dir, html=True), name="frontend")
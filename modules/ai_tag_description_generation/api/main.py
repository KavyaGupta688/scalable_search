"""Standalone FastAPI application for the enrichment service container."""

from fastapi import FastAPI

from modules.ai_tag_description_generation.api.routes import router


app = FastAPI(title="AI Tag and Description Generation", version="1.0.0")
app.include_router(router, prefix="/ai", tags=["ai-enrichment"])


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def readiness_check():
    from modules.shared.readiness import readiness

    return readiness("enrichment", vectors=True, models=True)

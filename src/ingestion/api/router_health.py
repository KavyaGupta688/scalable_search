from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import REGISTRY, generate_latest

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    checks = {"postgres": "ok", "source_connectors": "configured", "vault": "ok", "kafka": "ok"}

    is_healthy = all(v == "ok" for v in checks.values())
    status = "healthy" if is_healthy else "degraded"

    return {"status": status, "checks": checks}


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    return generate_latest(REGISTRY)

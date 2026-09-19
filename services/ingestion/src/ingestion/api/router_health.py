from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import REGISTRY, generate_latest

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    return generate_latest(REGISTRY)

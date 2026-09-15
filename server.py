"""SMSPRSM Platform API Server -- with Prometheus metrics + Audit Analytics.

Search requests (/search/*) are reverse-proxied to the Production Search
Service #2 running on SEARCH_SERVICE_URL (default http://localhost:8002).
"""
from __future__ import annotations
import json
import os
from typing import Optional

import httpx
from fastapi import FastAPI, Depends, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# -- Prometheus Instrumentation
from prometheus_fastapi_instrumentator import Instrumentator

# -- Module Routers
from modules.ai_tag_description_generation.api.routes import router as ai_router
from modules.download_auditing.api.routes import router as download_router
from modules.ingestion.api.routes import router as ingestion_router
from modules.shared.api import router as auth_router
from modules.shared.auth import require_roles

# -- Production Search Service #2 config
SEARCH_SERVICE_URL: str = os.getenv("SEARCH_SERVICE_URL", "http://localhost:8002")

app = FastAPI(
    title="SMSPRSM Platform API",
    version="0.2.0",
    description="Multimodal Data Platform with Enterprise Audit Intelligence",
)

# -- Prometheus: auto-instrument all routes, expose /metrics
Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    excluded_handlers=["/metrics", "/health"],
).instrument(app).expose(app, endpoint="/metrics", tags=["observability"])

# -- Application Routers
app.include_router(ingestion_router, prefix="/ingestion", tags=["ingestion"])
app.include_router(ai_router, prefix="/ai", tags=["ai-enrichment"])
app.include_router(download_router, prefix="/downloads", tags=["downloads"])
app.include_router(auth_router)


# -- Search Reverse Proxy > Production Search Service #2 (port 8002)
_search_client: Optional[httpx.AsyncClient] = None


def _get_search_client() -> httpx.AsyncClient:
    """Lazy-init a shared async HTTP client for search proxy requests."""
    global _search_client
    if _search_client is None or _search_client.is_closed:
        _search_client = httpx.AsyncClient(
            base_url=SEARCH_SERVICE_URL,
            timeout=httpx.Timeout(30.0, connect=5.0),
        )
    return _search_client


@app.api_route(
    "/search/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    tags=["search"],
    summary="Proxy to Production Search Service #2",
    include_in_schema=True,
)
async def search_proxy(request: Request, path: str) -> Response:
    """
    Transparent reverse proxy for all /search/* endpoints.
    Forwards to the Production Search Service #2 at SEARCH_SERVICE_URL (port 8002).

    Endpoints available via this proxy:
      POST /search               -- Hybrid RRF search (keyword + vector)
      POST /search/text          -- Keyword / metadata search
      POST /search/vector        -- Vector similarity search
      GET  /search/similar/{id}  -- Similar file search
      GET  /search/facets        -- Facet aggregations
      GET  /search/trending      -- Trending queries
      GET  /search/suggestions   -- Query autocomplete
    """
    client = _get_search_client()
    url = f"/{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    body = await request.body()
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length")
    }

    try:
        upstream = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
        )
    except httpx.ConnectError:
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "Production Search Service #2 is unavailable. "
                    f"Ensure the service is running on {SEARCH_SERVICE_URL}. "
                    "Start it with: cd services/search/backend && uvicorn app.main:app --port 8002"
                )
            },
        )
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={"detail": "Production Search Service #2 timed out."},
        )

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=dict(upstream.headers),
        media_type=upstream.headers.get("content-type"),
    )


@app.get(
    "/search",
    tags=["search"],
    include_in_schema=True,
    summary="Proxy to Production Search Service #2 root",
)
async def search_root_proxy(request: Request) -> Response:
    """Proxy GET /search to the search service root."""
    return await search_proxy(request, "")


# -- Health
@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


# -- Audit Analytics API
@app.get("/admin/audit/analytics", tags=["audit-intelligence"])
def audit_analytics(
    hours: int = 24,
    user: dict[str, str] = Depends(require_roles("admin")),
) -> JSONResponse:
    """
    Pre-aggregated audit analytics for the React AuditDashboardView.
    Returns KPI summary, module breakdown, error trend, top actors,
    peak usage by hour, and top search queries.
    """
    from modules.shared.audit_analytics import full_analytics
    data = full_analytics(hours=hours)
    return JSONResponse(content=data)


# -- Server Log Live Stream (SSE)
LOG_FILE_PATH = os.getenv("SERVER_LOG_PATH", "server_operational.log")


@app.get("/admin/server-logs/stream", tags=["audit-intelligence"])
def server_log_stream(
    lines: int = 100,
    user: dict[str, str] = Depends(require_roles("admin")),
) -> StreamingResponse:
    """
    SSE stream of the last N lines of server_operational.log.
    Also parses metrics from each line and updates Prometheus gauges.
    """
    from modules.shared.metrics import record_server_log_metric

    def _generate():
        try:
            with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
            tail = all_lines[-lines:]
            for raw_line in tail:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    parsed = json.loads(raw_line)
                    msg = parsed.get("message", {})
                    if isinstance(msg, dict):
                        record_server_log_metric(
                            subsystem=msg.get("subsystem", "unknown"),
                            event=msg.get("event", "UNKNOWN"),
                            latency_ms=msg.get("latency_ms"),
                            gpu_util_pct=msg.get("gpu_util_pct"),
                            level=parsed.get("level", "INFO"),
                        )
                except Exception:
                    pass
                yield f"data: {raw_line}\n\n"
        except FileNotFoundError:
            yield f"data: {json.dumps({'error': 'Log file not found', 'path': LOG_FILE_PATH})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# -- Frontend Static Files
dist_dir = "frontend/dist" if os.path.exists("frontend/dist") else "frontend"
app.mount("/", StaticFiles(directory=dist_dir, html=True), name="frontend")


def run() -> None:
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

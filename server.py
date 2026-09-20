"""Authenticated platform gateway; only the redesigned application is served."""

from __future__ import annotations
import os
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from sqlalchemy.exc import OperationalError, TimeoutError as DatabaseTimeoutError
from modules.shared.auth.dependencies import get_current_user, require_admin
from modules.shared.auth.routes import router as auth_router
from modules.shared.audit_api import router as audit_router
from modules.shared.integration import assertion

SERVICES = {
    name: os.getenv(name.upper() + "_SERVICE_URL", default)
    for name, default in {
        "ingestion": "http://localhost:8001",
        "search": "http://localhost:8002",
        "ai": "http://localhost:8003",
        "download": "http://localhost:8004",
    }.items()
}
HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
    "content-encoding",
}


@asynccontextmanager
async def lifespan(app):
    app.state.client = httpx.AsyncClient(
        timeout=httpx.Timeout(60, connect=5), follow_redirects=False
    )
    yield
    await app.state.client.aclose()


app = FastAPI(title="SMSPRSM Integrated Platform", lifespan=lifespan)
app.include_router(auth_router, prefix="/auth", tags=["authentication"])
app.include_router(audit_router, tags=["audit"])


def database_unavailable(request: Request):
    return JSONResponse(
        {"detail": "Database temporarily unavailable. Refresh the operation status before retrying."},
        status_code=503,
        headers={"X-Correlation-ID": getattr(request.state, "correlation_id", str(uuid.uuid4()))},
    )


@app.exception_handler(OperationalError)
@app.exception_handler(DatabaseTimeoutError)
async def database_error(request: Request, exc):
    return database_unavailable(request)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready(request: Request):
    import asyncio

    async def check(name, url):
        try:
            response = await request.app.state.client.get(url + "/ready", timeout=5)
            return name, response.status_code == 200
        except httpx.HTTPError:
            return name, False

    checks = dict(await asyncio.gather(*(check(k, v) for k, v in SERVICES.items())))
    return JSONResponse(
        {"services": checks}, status_code=200 if all(checks.values()) else 503
    )


async def forward(request: Request, service: str, user):
    path = request.url.path
    if path in ("/admin/connectors", "/documents"):
        path += "/"
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower()
        not in HOP_HEADERS
        | {"authorization", "cookie", "x-user-id", "x-user-role", "x-user-name"}
    }
    headers["Authorization"] = "Bearer " + assertion(
        user.id, str(user.role), service, email=user.email
    )
    headers["X-Correlation-ID"] = request.state.correlation_id
    url = SERVICES[service] + path
    if request.url.query:
        url += "?" + request.url.query
    try:
        upstream = await request.app.state.client.send(
            request.app.state.client.build_request(
                request.method, url, headers=headers, content=request.stream()
            ),
            stream=True,
        )
    except httpx.TimeoutException:
        raise HTTPException(504, "The service timed out. Please retry.") from None
    except httpx.HTTPError as exc:
        logging.getLogger(__name__).warning(
            "Upstream transport failure service=%s path=%s correlation=%s type=%s",
            service, path, request.state.correlation_id, type(exc).__name__,
        )
        raise HTTPException(503, "The service is unavailable. Please retry.") from None
    return StreamingResponse(
        upstream.aiter_bytes(),
        status_code=upstream.status_code,
        headers={
            k: v for k, v in upstream.headers.items()
            if k.lower() not in HOP_HEADERS or (
                k.lower() == "content-length" and not upstream.headers.get("content-encoding")
            )
        },
        background=BackgroundTask(upstream.aclose),
    )


@app.api_route("/admin/connectors", methods=["GET", "POST"])
@app.api_route(
    "/admin/connectors/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"]
)
@app.api_route("/admin/ingestion/{path:path}", methods=["GET", "POST"])
async def ingestion_admin(
    request: Request, path: str = "", user=Depends(require_admin)
):
    return await forward(request, "ingestion", user)


@app.api_route("/documents", methods=["GET"])
@app.api_route("/documents/{path:path}", methods=["GET"])
async def documents(request: Request, path: str = "", user=Depends(get_current_user)):
    if user.role != "admin":
        from modules.shared.catalog import require_downloadable

        try:
            document_id = str(uuid.UUID(path.split("/")[0]))
        except ValueError:
            raise HTTPException(403, "Administrator access required") from None
        if path.split("/")[1:] not in ([], ["content"]):
            raise HTTPException(403, "Use the protected content endpoint")
        await run_in_threadpool(require_downloadable, [document_id])
    return await forward(request, "ingestion", user)


@app.api_route("/ai/{path:path}", methods=["GET", "POST"])
async def ai(request: Request, path: str, user=Depends(require_admin)):
    return await forward(request, "ai", user)


@app.api_route("/search", methods=["POST"])
@app.api_route("/search/{path:path}", methods=["GET", "POST"])
@app.api_route("/files/{path:path}", methods=["GET"])
@app.api_route("/datasets/{path:path}", methods=["GET"])
@app.api_route("/events/{path:path}", methods=["POST"])
async def search(request: Request, path: str = "", user=Depends(get_current_user)):
    return await forward(request, "search", user)


@app.api_route("/downloads", methods=["GET"])
@app.api_route("/downloads/{path:path}", methods=["GET", "POST"])
async def downloads(request: Request, path: str = "", user=Depends(get_current_user)):
    return await forward(request, "download", user)


@app.get("/api/admin/overview")
def overview(user=Depends(require_admin)):
    from sqlalchemy import text
    from modules.shared.integration import database_engine

    with database_engine("ingestion").connect() as conn:
        documents = conn.execute(text("SELECT count(*) FROM documents")).scalar_one()
        sources = conn.execute(text("SELECT count(*) FROM connectors")).scalar_one()
        jobs = conn.execute(
            text("SELECT status,count(*) FROM ingestion_runs GROUP BY status")
        ).all()
        tasks = conn.execute(
            text(
                "SELECT status,count(*) FROM enrichment.enrichment_tasks GROUP BY status"
            )
        ).all()
    return {
        "documents": documents,
        "sources": sources,
        "ingestion": dict(jobs),
        "enrichment": dict(tasks),
    }


@app.middleware("http")
async def audit_requests(request: Request, call_next):
    request.state.correlation_id = str(uuid.uuid4())
    from modules.shared.auth.dependencies import get_auth_service

    actor, role = "anonymous", "anonymous"
    token = request.headers.get("authorization", "")
    if token.startswith("Bearer "):
        try:
            claims = await run_in_threadpool(lambda: get_auth_service().decode_token(token[7:]))
            actor, role = claims["sub"], claims["role"]
        except (OperationalError, DatabaseTimeoutError):
            return database_unavailable(request)
        except Exception:
            pass
    response = await call_next(request)
    actor, role = getattr(request.state, "auth_actor", (actor, role))
    response.headers["X-Correlation-ID"] = request.state.correlation_id
    path = request.url.path
    if path.startswith(
        ("/auth/", "/admin/connectors", "/admin/ingestion", "/ai/")
    ) or response.status_code in (401, 403):
        from modules.shared.audit import record

        if request.method != "GET" or response.status_code >= 400:
            try:
                await run_in_threadpool(
                    record,
                    request.method + " " + path,
                    actor,
                    "api",
                    path,
                    user_role=role,
                    status="SUCCESS"
                    if response.status_code < 400
                    else "DENIED"
                    if response.status_code in (401, 403)
                    else "FAILED",
                    correlation_id=request.state.correlation_id,
                    metadata={"http_status": response.status_code},
                )
            except (OperationalError, DatabaseTimeoutError):
                return database_unavailable(request)
    return response


DIST = Path(__file__).parent / "frontend" / "dist"


@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str):
    candidate = (DIST / path).resolve()
    if not candidate.is_relative_to(DIST.resolve()):
        raise HTTPException(404)
    if candidate.is_file():
        return FileResponse(candidate)
    if path not in {
        "admin",
        "admin/overview",
        "admin/search",
        "admin/data-sources",
        "admin/ingestion",
        "admin/enrichment",
        "admin/audit",
        "admin/users",
        "admin/downloads",
    } and path.split("/")[0] in {
        "api",
        "internal",
        "auth",
        "admin",
        "ai",
        "search",
        "files",
        "documents",
        "datasets",
        "downloads",
        "events",
        "ingestion",
    }:
        raise HTTPException(404, "API route not found")
    if not (DIST / "index.html").exists():
        raise HTTPException(503, "Frontend build is missing")
    return FileResponse(DIST / "index.html")


def run():
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000)

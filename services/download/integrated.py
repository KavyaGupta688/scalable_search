"""Canonical-document downloads, using ingestion's licensed source boundary."""

import hashlib
import json
import os
import tempfile
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, JSON, DateTime, select, text
from sqlalchemy.orm import declarative_base, Session

from modules.shared.integration import database_engine, internal_user, service_headers
from modules.shared.catalog import require_downloadable
from modules.shared.audit import record
from core.crypto import (
    create_tracking_payload,
    generate_watermark_token,
    verify_watermark_token,
)
from core.injectors.dispatcher import inject_watermark_bytes
from core.injectors.extractor import extract_token_from_bytes

Base = declarative_base()


class Job(Base):
    __tablename__ = "document_download_jobs"
    id = Column(String(36), primary_key=True)
    owner = Column(String(128), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    file_ids = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, default="building")
    error = Column(String(255))
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class JobItem(Base):
    __tablename__ = "document_download_items"
    id = Column(String(80), primary_key=True)
    job_id = Column(String(36), nullable=False, index=True)
    document_id = Column(String(36), nullable=False)
    status = Column(String(20), nullable=False)
    error = Column(String(255))


def file_progress(job_id, document_id, status, error=None):
    with Session(database_engine("download")) as session:
        session.merge(
            JobItem(
                id=job_id + ":" + document_id,
                job_id=job_id,
                document_id=document_id,
                status=status,
                error=error,
            )
        )
        session.commit()


ROOT = Path(os.getenv("DOWNLOAD_STAGING_DIR", "/tmp/smsprsm-downloads"))
MAX_FILE = int(os.getenv("DOWNLOAD_MAX_FILE_BYTES", str(128 * 1024**2)))
MAX_BATCH = int(os.getenv("DOWNLOAD_MAX_BATCH_BYTES", str(2 * 1024**3)))
INGESTION = os.getenv("INGESTION_SERVICE_URL", "http://localhost:8001")
if len(os.environ.get("WATERMARK_SECRET_KEY", "")) < 32:
    raise RuntimeError("WATERMARK_SECRET_KEY must contain at least 32 characters")
app = FastAPI(title="Integrated Download Service")
identity = internal_user("download", "data:download")


class BatchRequest(BaseModel):
    file_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)


def response(job):
    with Session(database_engine("download")) as session:
        rows = session.scalars(select(JobItem).where(JobItem.job_id == job.id)).all()
        items = [
            {"document_id": r.document_id, "status": r.status, "error": r.error}
            for r in rows
        ]
    return {
        "items": items,
        "progress": sum(i["status"] == "packaged" for i in items),
        "download_id": job.id,
        "status": job.status,
        "file_count": len(job.file_ids),
        "file_ids": job.file_ids,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "error": job.error,
        "download_url": f"/downloads/{job.id}/content"
        if job.status == "ready"
        else None,
    }


def owned(session, download_id, user):
    job = session.get(Job, str(download_id))
    if not job or (job.owner != user["sub"] and user["role"] != "admin"):
        raise HTTPException(404, "Download not found")
    return job


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/downloads/batch", status_code=202)
def create_batch(body: BatchRequest, user=Depends(identity)):
    ids = list(dict.fromkeys(str(i) for i in body.file_ids))
    require_downloadable(ids)
    with Session(database_engine("download"), expire_on_commit=False) as session:
        job = Job(
            id=str(uuid.uuid4()),
            owner=user["sub"],
            email=user.get("email", ""),
            file_ids=ids,
            status="building",
        )
        session.add(job)
        session.flush()
        from modules.shared.delivery import enqueue

        enqueue(
            session,
            "download:" + job.id,
            "audit",
            {
                "event_id": "download-" + job.id,
                "action": "DOWNLOAD_REQUEST",
                "actor": job.owner,
                "entity_type": "download",
                "entity_id": job.id,
                "metadata": {"file_count": len(ids)},
            },
        )
        session.commit()
        return response(job)


@app.get("/downloads")
def history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user=Depends(identity),
):
    with Session(database_engine("download")) as session:
        jobs = session.scalars(
            select(Job)
            .where(Job.owner == user["sub"])
            .order_by(Job.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return {"downloads": [response(j) for j in jobs]}


@app.get("/downloads/{download_id}")
def status(download_id: uuid.UUID, user=Depends(identity)):
    with Session(database_engine("download")) as session:
        return response(owned(session, download_id, user))


@app.get("/downloads/{download_id}/content")
def content(download_id: uuid.UUID, user=Depends(identity)):
    with Session(database_engine("download")) as session:
        job = owned(session, download_id, user)
        require_downloadable(job.file_ids)
        if job.status != "ready":
            raise HTTPException(409, "Download is not ready")
        path = ROOT / (job.id + ".zip")
        if not path.is_file():
            raise HTTPException(410, "Download package has expired; create a new batch")
        record("DOWNLOAD_DELIVERY_STARTED", user["sub"], "download", job.id)
        return FileResponse(
            path,
            filename="assets-" + job.id + ".zip",
            media_type="application/zip",
            headers={"Cache-Control": "no-store"},
        )


@app.post("/downloads/forensic/verify")
async def verify(
    file: UploadFile = File(...), user=Depends(internal_user("download", "admin:*"))
):
    data = await file.read(64 * 1024**2 + 1)
    if len(data) > 64 * 1024**2:
        raise HTTPException(413, "Verification limit is 64 MiB")
    token, detected = extract_token_from_bytes(data)
    valid, payload, message = (
        verify_watermark_token(token)
        if token
        else (False, None, "No metadata watermark")
    )
    from core.codec_forensics import inspect_signal
    from starlette.concurrency import run_in_threadpool

    signal = await run_in_threadpool(inspect_signal, data)
    record(
        "FORENSIC_VERIFY",
        user["sub"],
        "file",
        file.filename or "upload",
        metadata={"signature_valid": valid},
    )
    from database.models import ForensicAuditLog

    with Session(database_engine("download")) as session:
        log = session.get(ForensicAuditLog, payload.get("did")) if valid else None
        matched = bool(log and log.token_str == token)
    return {
        "audit_match": matched,
        "signature_valid": valid,
        "decoded_payload": payload if valid else None,
        "detected_format": detected,
        "message": message,
        "signal_watermark": signal,
    }


def package(job, session):
    require_downloadable(job.file_ids)
    ROOT.mkdir(parents=True, exist_ok=True)
    target = ROOT / (job.id + ".zip")
    total = 0
    # All-or-nothing archive; failed packages are never exposed.
    with tempfile.TemporaryDirectory(prefix=job.id + "-", dir=ROOT) as temporary:
        archive = Path(temporary) / "package.zip"
        manifest = []
        with (
            zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z,
            httpx.Client(timeout=120) as client,
        ):
            for document_id in job.file_ids:
                job._active_document_id = document_id
                file_progress(job.id, document_id, "processing")
                import shutil

                if shutil.disk_usage(ROOT).free < 3 * MAX_FILE:
                    raise ValueError("Insufficient temporary storage")
                headers = service_headers(
                    "ingestion", ["data:read", "data:download"], "download-worker"
                )
                meta_response = client.get(
                    INGESTION + "/documents/" + document_id, headers=headers
                )
                meta_response.raise_for_status()
                meta = meta_response.json()
                size = meta["size_bytes"]
                if size > MAX_FILE or total + size > MAX_BATCH:
                    raise ValueError("Selected files exceed download size limits")
                raw = bytearray()
                digest = hashlib.sha256()
                with client.stream(
                    "GET",
                    INGESTION + "/documents/" + document_id + "/content",
                    headers=headers,
                ) as stream:
                    stream.raise_for_status()
                    for chunk in stream.iter_bytes():
                        if len(raw) + len(chunk) > min(size, MAX_FILE):
                            raise ValueError("Source size changed")
                        raw.extend(chunk)
                        digest.update(chunk)
                if len(raw) != size or digest.hexdigest() != meta["checksum_sha256"]:
                    raise ValueError("Source integrity check failed")
                name = Path(meta["source_ref"].replace("\\", "/")).name
                name = (
                    "".join(c if c.isalnum() or c in "._- " else "_" for c in name)[
                        :160
                    ]
                    or "asset"
                )
                filename = document_id + "_" + name
                payload = create_tracking_payload(
                    user_id=job.owner,
                    user_email=job.email,
                    s3_key=document_id,
                    client_ip="internal",
                    extra_metadata={"job_id": job.id, "document_id": document_id},
                )
                payload["did"] = str(uuid.uuid5(uuid.UUID(job.id), document_id))
                token = generate_watermark_token(payload)
                output = inject_watermark_bytes(bytes(raw), token, file_identifier=name)
                file_progress(job.id, document_id, "packaged")
                total += len(output)
                if total > MAX_BATCH:
                    raise ValueError("Package exceeds its size limit")
                z.writestr(filename, output)
                manifest.append(
                    {
                        "document_id": document_id,
                        "filename": filename,
                        "download_id": payload["did"],
                    }
                )
                from database.models import ForensicAuditLog

                session.merge(
                    ForensicAuditLog(
                        download_id=payload["did"],
                        user_id=job.owner,
                        user_email=job.email,
                        s3_key=document_id,
                        timestamp=payload["ts"],
                        iso_timestamp=datetime.fromtimestamp(
                            payload["ts"], timezone.utc
                        ).isoformat(),
                        client_ip="internal",
                        token_str=token,
                        token_signature=token.rsplit(".", 1)[1],
                        file_size_bytes=len(output),
                        status="PACKAGED",
                        notes=job.id,
                    )
                )
                from modules.shared.delivery import enqueue

                enqueue(
                    session,
                    "package:" + payload["did"],
                    "audit",
                    {
                        "event_id": "package-" + payload["did"],
                        "action": "DOWNLOAD_PACKAGED",
                        "actor": job.owner,
                        "entity_type": "document",
                        "entity_id": document_id,
                        "correlation_id": job.id,
                        "metadata": {"job_id": job.id, "watermark_id": payload["did"]},
                    },
                )
            z.writestr("manifest.json", json.dumps(manifest, indent=2))
        require_downloadable(job.file_ids)
        archive.replace(target)


def work_once():
    with Session(database_engine("download")) as session, session.begin():
        job = session.scalar(
            select(Job)
            .where(Job.status == "building")
            .order_by(Job.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return False
        try:
            package(job, session)
            job.status = "ready"
            # Committed once with the job outcome; crash retries roll back counters too.
            for document_id in job.file_ids:
                session.execute(
                    text(
                        "UPDATE search.file_metadata SET download_count=download_count+1 WHERE file_id=:id"
                    ),
                    {"id": document_id},
                )
                session.execute(
                    text(
                        "UPDATE search.datasets SET download_count=download_count+1, popularity_score=popularity_score+2 WHERE id=(SELECT dataset_id FROM search.file_metadata WHERE file_id=:id)"
                    ),
                    {"id": document_id},
                )
        except Exception as exc:
            job.status = "failed"
            if getattr(job, "_active_document_id", None):
                file_progress(
                    job.id,
                    job._active_document_id,
                    "failed",
                    str(exc)[:255]
                    if isinstance(exc, ValueError)
                    else type(exc).__name__,
                )
            if isinstance(exc, HTTPException):
                reason = str(exc.detail)
            elif isinstance(exc, httpx.HTTPStatusError):
                reason = f"Source service returned HTTP {exc.response.status_code}"
            elif isinstance(exc, ValueError):
                reason = str(exc)
            else:
                reason = type(exc).__name__
            job.error = ("Unable to package selected documents: " + reason)[:255]
            with Session(database_engine("download")) as progress_session:
                processed = set(
                    progress_session.scalars(
                        select(JobItem.document_id).where(JobItem.job_id == job.id)
                    )
                )
            for document_id in set(job.file_ids) - processed:
                file_progress(
                    job.id,
                    document_id,
                    "skipped",
                    "Batch stopped after an earlier failure",
                )
        job.updated_at = datetime.now(timezone.utc)
        from modules.shared.delivery import enqueue

        enqueue(
            session,
            "outcome:" + job.id,
            "audit",
            {
                "event_id": "outcome-" + job.id,
                "action": "DOWNLOAD_" + job.status.upper(),
                "actor": job.owner,
                "entity_type": "download",
                "entity_id": job.id,
                "correlation_id": job.id,
                "status": "SUCCESS" if job.status == "ready" else "FAILED",
            },
        )
        return True


if __name__ == "__main__":
    while True:
        work_once()
        # Packages expire after one day. Existing external/vendor files are never touched.
        if ROOT.exists():
            for path in ROOT.glob("*.zip"):
                if path.stat().st_mtime < time.time() - 86400:
                    path.unlink()
            # Only task-owned UUID-prefixed temporary directories can be orphaned.
            import shutil

            for path in ROOT.iterdir():
                if not path.is_dir() or path.stat().st_mtime >= time.time() - 86400:
                    continue
                try:
                    uuid.UUID(path.name[:36])
                except ValueError:
                    continue
                if path.resolve().is_relative_to(ROOT.resolve()):
                    shutil.rmtree(path)
        time.sleep(2)


@app.get("/ready")
def readiness_check():
    from modules.shared.readiness import readiness

    return readiness("download")

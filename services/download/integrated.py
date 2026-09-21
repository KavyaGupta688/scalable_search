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
from sqlalchemy import Column, String, JSON, DateTime, func, select, text
from sqlalchemy.orm import declarative_base, Session

from modules.shared import download_limits
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
# Limits are shared with Search, which plans downloads against the same numbers.
MAX_FILE = download_limits.MAX_FILE_BYTES  # largest single file
MAX_BATCH = download_limits.PART_BYTES  # size of one archive part; bigger requests are split
MAX_FILES = download_limits.MAX_FILES  # files per request
MAX_TOTAL = download_limits.MAX_TOTAL_BYTES  # bytes per request, across all parts
INGESTION = os.getenv("INGESTION_SERVICE_URL", "http://localhost:8001")
if len(os.environ.get("WATERMARK_SECRET_KEY", "")) < 32:
    raise RuntimeError("WATERMARK_SECRET_KEY must contain at least 32 characters")
app = FastAPI(title="Integrated Download Service")
identity = internal_user("download", "data:download")


class BatchRequest(BaseModel):
    file_ids: list[uuid.UUID] = Field(min_length=1, max_length=MAX_FILES)


# Jobs at most this large list every file in `items`. Larger jobs list only the files that
# did not package, so polling a 10,000-file request does not return 10,000 rows.
FULL_ITEM_LISTING = 200


def archive_parts(job_id):
    """Archive files of a finished job, in part order. A single-part job keeps the plain name."""
    single = ROOT / (job_id + ".zip")
    if single.is_file():
        return [single]
    return sorted(ROOT.glob(job_id + ".part*.zip"))


def response(job, estimated_bytes=None):
    with Session(database_engine("download")) as session:
        progress = session.scalar(
            select(func.count())
            .select_from(JobItem)
            .where(JobItem.job_id == job.id, JobItem.status == "packaged")
        )
        query = select(JobItem).where(JobItem.job_id == job.id)
        if len(job.file_ids) > FULL_ITEM_LISTING:
            query = query.where(JobItem.status.in_(("failed", "skipped")) | JobItem.error.isnot(None))
        rows = session.scalars(query).all()
        items = [
            {"document_id": r.document_id, "status": r.status, "error": r.error}
            for r in rows
        ]
    parts = []
    if job.status == "ready":
        for index, path in enumerate(archive_parts(job.id), start=1):
            try:
                size = path.stat().st_size
            except OSError:  # expired between listing and stat
                continue
            parts.append({
                "index": index,
                "size_bytes": size,
                "download_url": f"/downloads/{job.id}/content?part={index}",
            })
    result = {
        "items": items,
        "progress": progress or 0,
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
        "parts": parts,
        "part_count": len(parts),
        "archive_bytes": sum(part["size_bytes"] for part in parts),
    }
    if estimated_bytes is not None:
        result["estimated_bytes"] = estimated_bytes
    return result


def owned(session, download_id, user):
    job = session.get(Job, str(download_id))
    if not job or (job.owner != user["sub"] and user["role"] != "admin"):
        raise HTTPException(404, "Download not found")
    return job


@app.get("/health")
def health():
    return {"status": "ok"}


def human(size):
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


def selection_size(ids):
    """(total bytes, largest file, files over the per-file limit) from the search catalog."""
    from sqlalchemy import bindparam

    statement = text(
        "SELECT coalesce(sum(file_size), 0), coalesce(max(file_size), 0), "
        "count(*) FILTER (WHERE file_size > :limit) "
        "FROM search.file_metadata WHERE file_id IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    with database_engine("search").connect() as conn:
        total, largest, oversized = conn.execute(
            statement, {"ids": ids, "limit": MAX_FILE}
        ).one()
    return int(total), int(largest), int(oversized)


@app.post("/downloads/batch", status_code=202)
def create_batch(body: BatchRequest, user=Depends(identity)):
    ids = list(dict.fromkeys(str(i) for i in body.file_ids))
    require_downloadable(ids)
    total, largest, oversized = selection_size(ids)
    # Reject up front, with a reason the user can act on, instead of failing hours into packaging.
    if oversized:
        raise HTTPException(
            422,
            f"{oversized} selected file(s) exceed the per-file limit of {human(MAX_FILE)}; "
            "remove them and try again.",
        )
    if total > MAX_TOTAL:
        raise HTTPException(
            413,
            f"The selection is {human(total)}; the limit is {human(MAX_TOTAL)} per request. "
            "Select fewer files.",
        )
    import shutil

    ROOT.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(ROOT).free < total + 3 * MAX_FILE:
        raise HTTPException(
            503, "Not enough temporary storage to prepare this download right now."
        )
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
        return response(job, estimated_bytes=total)


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
def content(
    download_id: uuid.UUID, part: int = Query(1, ge=1), user=Depends(identity)
):
    with Session(database_engine("download")) as session:
        job = owned(session, download_id, user)
        require_downloadable(job.file_ids)
        if job.status != "ready":
            raise HTTPException(409, "Download is not ready")
        parts = archive_parts(job.id)
        if not parts:
            raise HTTPException(410, "Download package has expired; create a new batch")
        if part > len(parts):
            raise HTTPException(404, f"Download has {len(parts)} part(s); part {part} does not exist")
        path = parts[part - 1]
        record(
            "DOWNLOAD_DELIVERY_STARTED", user["sub"], "download", job.id,
            metadata={"part": part, "parts": len(parts)},
        )
        return FileResponse(
            path,
            filename="assets-" + job.id + ".zip"
            if len(parts) == 1
            else f"assets-{job.id}-part{part:04d}-of-{len(parts):04d}.zip",
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


class PartWriter:
    """Writes files into consecutive archive parts, starting a new part when one is full.

    Each part is a complete zip with its own manifest.json, so parts can be saved and
    unpacked independently.
    """

    def __init__(self, directory, limit):
        self.directory, self.limit = directory, limit
        self.paths, self._zip, self._used, self._manifest = [], None, 0, []

    def add(self, filename, data, entry):
        if self._zip is not None and self._used + len(data) > self.limit:
            self._finish()
        if self._zip is None:
            self._start()
        self._zip.writestr(filename, data)
        self._used += len(data)
        self._manifest.append(entry)

    def _start(self):
        path = self.directory / f"part{len(self.paths) + 1:04d}.zip"
        self.paths.append(path)
        self._zip = zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED)
        self._used, self._manifest = 0, []

    def _finish(self):
        self._zip.writestr("manifest.json", json.dumps(self._manifest, indent=2))
        self._zip.close()
        self._zip = None

    def close(self):
        if self._zip is not None:
            self._finish()
        return list(self.paths)

    def abort(self):
        if self._zip is not None:
            self._zip.close()
            self._zip = None


def publish(job_id, parts):
    """Moves finished parts into place. A single part keeps the plain archive name."""
    targets = (
        [ROOT / (job_id + ".zip")]
        if len(parts) == 1
        else [ROOT / f"{job_id}.part{i:04d}.zip" for i in range(1, len(parts) + 1)]
    )
    moved = []
    try:
        for source, target in zip(parts, targets):
            source.replace(target)
            moved.append(target)
    except Exception:
        for target in moved:  # never leave a partial archive set behind
            target.unlink(missing_ok=True)
        raise


def package(job, session):
    require_downloadable(job.file_ids)
    ROOT.mkdir(parents=True, exist_ok=True)
    total = 0
    # All-or-nothing: parts are built in a temporary directory and only exposed once every
    # file is packaged; failed packages are never exposed.
    with tempfile.TemporaryDirectory(prefix=job.id + "-", dir=ROOT) as temporary:
        writer = PartWriter(Path(temporary), MAX_BATCH)
        try:
            with httpx.Client(timeout=120) as client:
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
                    if size > MAX_FILE or total + size > MAX_TOTAL:
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
                    if total > MAX_TOTAL:
                        raise ValueError("Package exceeds its size limit")
                    writer.add(
                        filename,
                        output,
                        {
                            "document_id": document_id,
                            "filename": filename,
                            "download_id": payload["did"],
                        },
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
            parts = writer.close()
        finally:
            writer.abort()
        require_downloadable(job.file_ids)
        publish(job.id, parts)


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

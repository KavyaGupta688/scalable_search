"""
REST & Streaming API Endpoints for the Watermarking Gateway.
Supports synchronous on-the-fly streaming across Images, Audio, and Video,
and asynchronous Celery + Redis background processing.
"""
import sys
import os
import io
import uuid
import json
import zipfile
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import APIRouter, Query, Request, UploadFile, File, Form, HTTPException, Body
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from pydantic import BaseModel

from core.crypto import create_tracking_payload, generate_watermark_token, verify_watermark_token
from core.s3_client import s3_client
from core.injectors.dispatcher import inject_watermark_bytes, inject_watermark_stream
from core.injectors.extractor import extract_token_from_bytes
from core.celery_app import celery_app
from database.db import db
from config import ASYNC_STORAGE_DIR

router = APIRouter()


class AsyncDownloadRequest(BaseModel):
    s3_keys: List[str]
    user_id: str = "USR-9842"
    user_email: str = "data_scientist@enterprise.com"
    user_role: str = "ML Research Engineer"


@router.get("/system/health")
async def system_health():
    """Returns connectivity status for PostgreSQL/AWS RDS, Redis, and S3."""
    db_health = db.get_health_status()
    
    # Test Redis connectivity
    redis_status = {"connected": False}
    try:
        import redis
        from config import REDIS_HOST, REDIS_PORT
        r = redis.Redis(host=REDIS_HOST, port=int(REDIS_PORT), socket_connect_timeout=2)
        r.ping()
        redis_status = {"connected": True, "host": f"{REDIS_HOST}:{REDIS_PORT}"}
    except Exception as e:
        redis_status = {"connected": False, "error": str(e), "hint": "Run redis-server or docker compose up -d"}

    return {
        "database": db_health,
        "redis_broker": redis_status,
        "s3_storage": {
            "bucket": s3_client.bucket_name,
            "mock_mode": s3_client.use_mock
        }
    }


@router.get("/s3/files")
async def list_s3_files(prefix: str = ""):
    """Lists files available in S3 or local mock store."""
    try:
        files = s3_client.list_files(prefix=prefix)
        return {
            "bucket": s3_client.bucket_name,
            "is_mock_mode": s3_client.use_mock,
            "count": len(files),
            "files": files
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "bucket": s3_client.bucket_name,
                "is_mock_mode": s3_client.use_mock,
                "error": str(e),
                "hint": "Please check your AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and S3_BUCKET_NAME in your .env file.",
                "files": []
            }
        )


@router.get("/download")
async def stream_watermarked_download(
    request: Request,
    s3_key: str = Query(..., description="S3 file key to download"),
    user_id: str = Query("USR-9842", description="ID of the user initiating download"),
    user_email: str = Query("data_scientist@enterprise.com", description="Email of the user"),
    user_role: str = Query("ML Research Engineer", description="User role in the platform")
):
    """
    Synchronous streaming endpoint.
    Pulls raw Image/Audio/Video file from S3, embeds cryptographic watermark on-the-fly,
    records forensic audit log in AWS RDS PostgreSQL, and streams directly to client.
    """
    try:
        raw_stream, content_length, content_type = s3_client.get_file_stream(s3_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File '{s3_key}' not found in S3 bucket.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 access error: {str(e)}")

    client_ip = request.client.host if request.client else "127.0.0.1"

    # 1. Create cryptographic tracking payload & token
    payload = create_tracking_payload(
        user_id=user_id,
        user_email=user_email,
        s3_key=s3_key,
        client_ip=client_ip,
        extra_metadata={"role": user_role, "gateway_version": "2.0"}
    )
    token_str = generate_watermark_token(payload)

    # 2. Record download in AWS RDS PostgreSQL / SQLite Database
    db.record_download(
        download_id=payload["did"],
        user_id=user_id,
        user_email=user_email,
        s3_key=s3_key,
        timestamp=payload["ts"],
        client_ip=client_ip,
        token_str=token_str,
        file_size_bytes=content_length,
        status="STREAMING_DELIVERED"
    )

    # 3. Stream with on-the-fly format-specific binary injection (Image, Audio, Video)
    output_stream = inject_watermark_stream(raw_stream, token_str, file_identifier=s3_key)

    filename = s3_key.split("/")[-1]
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Watermark-Download-ID": payload["did"],
        "X-Watermark-Status": "Injected-Metadata-Only",
        "X-Watermark-Pixel-Distortion": "0%",
        "X-Watermark-Signal-Distortion": "0.000%"
    }

    return StreamingResponse(
        output_stream,
        media_type=content_type,
        headers=headers
    )


@router.post("/download/zip")
async def download_direct_zip(req: AsyncDownloadRequest, request: Request):
    """
    Direct multi-file ZIP streaming endpoint for Images, Audio, and Video.
    Watermarks all selected S3 assets in memory with 0% distortion,
    records individual forensic audit trails in AWS RDS,
    and streams a packaged ZIP archive directly to the client.
    """
    if not req.s3_keys:
        raise HTTPException(status_code=400, detail="No files selected for download.")

    client_ip = request.client.host if request.client else "127.0.0.1"
    zip_buffer = io.BytesIO()

    try:
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_out:
            for s3_key in req.s3_keys:
                try:
                    stream, content_len, ctype = s3_client.get_file_stream(s3_key)
                    raw_bytes = b"".join(stream)

                    payload = create_tracking_payload(
                        user_id=req.user_id,
                        user_email=req.user_email,
                        s3_key=s3_key,
                        client_ip=client_ip,
                        extra_metadata={"role": req.user_role, "mode": "DIRECT_ZIP_STREAM"}
                    )
                    token_str = generate_watermark_token(payload)

                    # Multi-modal injection (Image, Audio, Video)
                    watermarked_bytes = inject_watermark_bytes(raw_bytes, token_str, file_identifier=s3_key)

                    # Save to database audit trail
                    db.record_download(
                        download_id=payload["did"],
                        user_id=req.user_id,
                        user_email=req.user_email,
                        s3_key=s3_key,
                        timestamp=payload["ts"],
                        client_ip=client_ip,
                        token_str=token_str,
                        file_size_bytes=len(watermarked_bytes),
                        status="DIRECT_ZIP_DELIVERED"
                    )

                    file_basename = Path(s3_key).name
                    zip_out.writestr(file_basename, watermarked_bytes)
                except Exception as file_err:
                    print(f"[ZIP Multi-Download Warning] Skipping file '{s3_key}': {file_err}")

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()
        zip_filename = f"s3_bundle_{len(req.s3_keys)}_files.zip"

        headers = {
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
            "Content-Length": str(len(zip_bytes)),
            "X-Watermark-Status": "Batch-Injected-Metadata-Only",
            "X-Watermark-Pixel-Distortion": "0%",
            "X-Watermark-Signal-Distortion": "0.000%"
        }

        return StreamingResponse(
            io.BytesIO(zip_bytes),
            media_type="application/zip",
            headers=headers
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate ZIP package: {str(e)}")


@router.post("/async/download")
async def trigger_async_download(req: AsyncDownloadRequest, request: Request):
    """
    Dispatches a Celery + Redis background job to download, watermark, and package multi-modal assets.
    Returns the job_id for real-time progress polling.
    """
    if not req.s3_keys:
        raise HTTPException(status_code=400, detail="No s3_keys specified.")

    job_id = str(uuid.uuid4())
    client_ip = request.client.host if request.client else "127.0.0.1"

    # Create job entry in AWS RDS PostgreSQL
    db.create_async_job(
        job_id=job_id,
        user_id=req.user_id,
        user_email=req.user_email,
        s3_keys=req.s3_keys
    )

    try:
        # Dispatch Celery background task
        from core.tasks import process_async_watermarked_package
        task = process_async_watermarked_package.delay(
            job_id=job_id,
            s3_keys=req.s3_keys,
            user_id=req.user_id,
            user_email=req.user_email,
            user_role=req.user_role,
            client_ip=client_ip
        )
        celery_task_id = task.id
    except Exception as e:
        print(f"[Celery Dispatch Warning] Redis broker unreachable: {e}. Executing inline.")
        try:
            from core.tasks import process_async_watermarked_package
            process_async_watermarked_package(
                job_id=job_id,
                s3_keys=req.s3_keys,
                user_id=req.user_id,
                user_email=req.user_email,
                user_role=req.user_role,
                client_ip=client_ip
            )
            celery_task_id = "INLINE_EXECUTION"
        except Exception as inner_e:
            db.update_job_progress(job_id, status="FAILED", progress_pct=0, error_message=str(inner_e))
            raise HTTPException(status_code=500, detail=f"Job processing error: {str(inner_e)}")

    return {
        "job_id": job_id,
        "celery_task_id": celery_task_id,
        "status": "QUEUED",
        "total_files": len(req.s3_keys),
        "status_url": f"/api/async/job/{job_id}",
        "download_url": f"/api/async/package/{job_id}"
    }


@router.get("/async/job/{job_id}")
async def get_async_job_status(job_id: str):
    """Polls real-time progress from AWS RDS PostgreSQL and Redis."""
    job_record = db.get_job(job_id)
    if not job_record:
        raise HTTPException(status_code=404, detail="Job not found.")

    return {
        "job": job_record,
        "is_ready": job_record["status"] == "COMPLETED",
        "download_url": f"/api/async/package/{job_id}" if job_record["status"] == "COMPLETED" else None
    }


@router.get("/async/package/{job_id}")
async def download_async_package(job_id: str):
    """Downloads the completed watermarked zip package from staging."""
    job_record = db.get_job(job_id)
    if not job_record:
        raise HTTPException(status_code=404, detail="Job not found.")

    if job_record["status"] != "COMPLETED" or not job_record["output_filename"]:
        raise HTTPException(status_code=400, detail="Package is not ready yet.")

    file_path = ASYNC_STORAGE_DIR / job_record["output_filename"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Package file missing on server.")

    return FileResponse(
        path=str(file_path),
        filename=job_record["output_filename"],
        media_type="application/zip"
    )


@router.post("/forensic/verify")
async def verify_leaked_file(file: UploadFile = File(...)):
    """
    Forensic leak inspection endpoint for Images, Audio, and Video files.
    Extracts metadata token, validates cryptographic signature, and looks up the AWS RDS audit trail.
    """
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    extracted_token, detected_format = extract_token_from_bytes(file_bytes)

    if not extracted_token:
        return JSONResponse(
            status_code=200,
            content={
                "watermark_found": False,
                "filename": file.filename,
                "detected_format": detected_format,
                "message": "No enterprise watermark metadata was found in this file."
            }
        )

    is_valid, payload, verify_msg = verify_watermark_token(extracted_token)

    audit_record = None
    if payload and "did" in payload:
        audit_record = db.find_by_download_id(payload["did"])

    return JSONResponse(
        status_code=200,
        content={
            "watermark_found": True,
            "signature_valid": is_valid,
            "verification_status": verify_msg,
            "detected_format": detected_format,
            "filename_analyzed": file.filename,
            "file_size_bytes": len(file_bytes),
            "embedded_token": extracted_token,
            "decoded_payload": payload,
            "forensic_audit_trail": audit_record
        }
    )


@router.get("/audit-logs")
async def get_forensic_logs(limit: int = 50):
    """Retrieves audit download logs from AWS RDS PostgreSQL."""
    logs = db.list_all_logs(limit=limit)
    return {
        "database_engine": db.db_type,
        "total_records": len(logs),
        "logs": logs
    }

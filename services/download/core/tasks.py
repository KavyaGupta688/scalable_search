"""
Celery Background Tasks for S3 Ingestion, Multi-Modal Watermarking & Batch Packaging.
"""
import sys
import io
import time
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.celery_app import celery_app
from core.crypto import create_tracking_payload, generate_watermark_token
from core.s3_client import s3_client
from core.injectors.dispatcher import inject_watermark_bytes
from database.db import db
from config import ASYNC_STORAGE_DIR


@celery_app.task(bind=True, name="core.tasks.process_async_watermarked_package")
def process_async_watermarked_package(
    self,
    job_id: str,
    s3_keys: List[str],
    user_id: str,
    user_email: str,
    user_role: str = "Researcher",
    client_ip: str = "127.0.0.1"
) -> Dict[str, Any]:
    """
    Asynchronous Celery worker task:
    1. Downloads files (Images, Audio, Video) from S3.
    2. Embeds cryptographic tracking tokens on-the-fly into headers (0% signal distortion).
    3. Packages results into a ZIP archive in async staging storage.
    4. Writes forensic audit trails directly into AWS RDS PostgreSQL.
    5. Updates real-time progress via Redis.
    """
    total_files = len(s3_keys)
    db.update_job_progress(job_id, status="PROCESSING", progress_pct=5)
    
    if hasattr(self, 'request') and self.request and self.request.id:
        try:
            self.update_state(
                state="PROGRESS",
                meta={"current": 0, "total": total_files, "percent": 5, "status": "Starting S3 stream..."}
            )
        except Exception:
            pass

    zip_filename = f"watermarked_package_{job_id[:8]}.zip"
    zip_path = ASYNC_STORAGE_DIR / zip_filename
    watermarked_records = []

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_out:
            for idx, s3_key in enumerate(s3_keys):
                file_basename = Path(s3_key).name

                # 1. Fetch file stream from S3
                stream, content_len, ctype = s3_client.get_file_stream(s3_key)
                raw_bytes = b"".join(stream)

                # 2. Generate Cryptographic Token
                payload = create_tracking_payload(
                    user_id=user_id,
                    user_email=user_email,
                    s3_key=s3_key,
                    client_ip=client_ip,
                    extra_metadata={"role": user_role, "async_job_id": job_id}
                )
                token_str = generate_watermark_token(payload)

                # 3. Inject Watermark into Metadata Headers (0% Signal Distortion)
                watermarked_bytes = inject_watermark_bytes(raw_bytes, token_str, file_identifier=s3_key)

                # 4. Save into ZIP
                zip_out.writestr(file_basename, watermarked_bytes)

                # 5. Persist Forensic Record in AWS RDS PostgreSQL
                db.record_download(
                    download_id=payload["did"],
                    user_id=user_id,
                    user_email=user_email,
                    s3_key=s3_key,
                    timestamp=payload["ts"],
                    client_ip=client_ip,
                    token_str=token_str,
                    file_size_bytes=len(watermarked_bytes),
                    status="CELERY_ASYNC_DELIVERED",
                    notes=f"Async Job {job_id}"
                )

                watermarked_records.append({
                    "s3_key": s3_key,
                    "download_id": payload["did"],
                    "file_size": len(watermarked_bytes)
                })

                # 6. Calculate Progress & Update State
                progress = int(((idx + 1) / total_files) * 90) + 5
                if hasattr(self, 'request') and self.request and self.request.id:
                    try:
                        self.update_state(
                            state="PROGRESS",
                            meta={
                                "current": idx + 1,
                                "total": total_files,
                                "percent": progress,
                                "current_file": file_basename,
                                "status": f"Processed {idx + 1}/{total_files} assets"
                            }
                        )
                    except Exception:
                        pass
                db.update_job_progress(job_id, status="PROCESSING", progress_pct=progress)

        final_size = zip_path.stat().st_size
        db.update_job_progress(
            job_id,
            status="COMPLETED",
            progress_pct=100,
            output_filename=zip_filename,
            file_size_bytes=final_size
        )

        return {
            "status": "COMPLETED",
            "job_id": job_id,
            "filename": zip_filename,
            "file_size_bytes": final_size,
            "total_files": total_files,
            "records": watermarked_records
        }

    except Exception as e:
        error_msg = str(e)
        db.update_job_progress(
            job_id,
            status="FAILED",
            progress_pct=0,
            error_message=error_msg
        )
        if hasattr(self, 'request') and self.request and self.request.id:
            try:
                self.update_state(
                    state="FAILURE",
                    meta={"error": error_msg}
                )
            except Exception:
                pass
        raise e

"""
High-Performance S3 Chunked Streaming Client.

Handles memory-efficient streaming from AWS S3 using boto3.
Automatically provides a realistic Local Mock/Simulator mode when AWS credentials
are not active, allowing full end-to-end evaluation without cloud dependencies.
"""
import io
import os
from pathlib import Path
from typing import Iterator, List, Dict, Any, Optional, Tuple
from config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION,
    S3_BUCKET_NAME,
    USE_MOCK_S3,
    LOCAL_MOCK_DIR,
    STREAM_CHUNK_SIZE
)

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


MIME_MAP = {
    # Images
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
    "tiff": "image/tiff",
    "bmp": "image/bmp",
    # Audio
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "flac": "audio/flac",
    "ogg": "audio/ogg",
    "m4a": "audio/mp4",
    "aac": "audio/aac",
    # Video
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "mkv": "video/x-matroska",
    "webm": "video/webm",
    "avi": "video/x-msvideo",
    "m4v": "video/x-m4v",
    # Data
    "parquet": "application/x-parquet",
    "zip": "application/zip",
    "json": "application/json",
    "csv": "text/csv"
}


class S3StreamClient:
    def __init__(self):
        self.use_mock = USE_MOCK_S3
        self.bucket_name = S3_BUCKET_NAME
        self.s3 = None

        if not self.use_mock:
            import boto3
            kwargs = {"region_name": AWS_REGION}
            if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
                kwargs["aws_access_key_id"] = AWS_ACCESS_KEY_ID
                kwargs["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY
            try:
                self.s3 = boto3.client("s3", **kwargs)
            except Exception as e:
                print(f"[S3 Warning] Could not initialize boto3 client: {e}")
        else:
            self._ensure_sample_datasets()

    def _ensure_sample_datasets(self):
        """Generates realistic sample AI datasets if mock mode is active."""
        LOCAL_MOCK_DIR.mkdir(parents=True, exist_ok=True)
        
        sample_files = [
            ("autonomous_driving/camera_front_001.png", "PNG", (1920, 1080), (30, 45, 60), "Autonomous Vision Frame #001"),
            ("medical_imaging/mri_brain_scan_axial.jpg", "JPEG", (1024, 1024), (15, 15, 20), "Brain MRI Scan Axial Slice 42"),
        ]

        if HAS_PIL:
            for rel_path, img_format, size, bg_color, label in sample_files:
                target_path = LOCAL_MOCK_DIR / rel_path
                if not target_path.exists():
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    img = Image.new("RGB", size, color=bg_color)
                    draw = ImageDraw.Draw(img)
                    draw.rectangle([(50, 50), (size[0]-50, 120)], fill=(0, 0, 0, 180), outline=(255, 255, 255))
                    draw.text((70, 70), f"S3 REPO: {label}", fill=(255, 255, 255))
                    img.save(str(target_path), format=img_format)

    def list_files(self, prefix: str = "") -> List[Dict[str, Any]]:
        """Lists available files in the live S3 bucket with full pagination."""
        results = []
        if not self.use_mock and self.s3:
            try:
                paginator = self.s3.get_paginator("list_objects_v2")
                pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
                for page in pages:
                    for item in page.get("Contents", []):
                        if item["Key"].endswith("/"):
                            continue
                        results.append({
                            "key": item["Key"],
                            "size_bytes": item["Size"],
                            "last_modified": item["LastModified"].isoformat() if hasattr(item["LastModified"], "isoformat") else str(item["LastModified"]),
                            "is_mock": False
                        })
                return results
            except Exception as e:
                print(f"[AWS S3 Error] Failed to list bucket '{self.bucket_name}': {e}")
                raise RuntimeError(f"Could not connect to S3 bucket '{self.bucket_name}': {str(e)}")

        # Local mock directory listing (only if USE_MOCK_S3 is explicitly true)
        if LOCAL_MOCK_DIR.exists():
            for p in LOCAL_MOCK_DIR.rglob("*"):
                if p.is_file():
                    rel_key = p.relative_to(LOCAL_MOCK_DIR).as_posix()
                    if prefix and not rel_key.startswith(prefix):
                        continue
                    results.append({
                        "key": rel_key,
                        "size_bytes": p.stat().st_size,
                        "last_modified": p.stat().st_mtime,
                        "is_mock": True
                    })
        return results

    def get_file_stream(self, s3_key: str) -> Tuple[Iterator[bytes], int, str]:
        """
        Retrieves a chunked byte generator for the requested S3 key.
        Returns: (chunk_iterator, content_length_bytes, content_type)
        """
        ext = s3_key.lower().split(".")[-1]
        content_type = MIME_MAP.get(ext, "application/octet-stream")

        if not self.use_mock:
            if not self.s3:
                raise RuntimeError("S3 client not initialized. Please verify AWS credentials and region.")
            try:
                s3_obj = self.s3.get_object(Bucket=self.bucket_name, Key=s3_key)
                content_length = s3_obj.get("ContentLength", 0)
                body = s3_obj["Body"]

                def s3_generator():
                    while chunk := body.read(STREAM_CHUNK_SIZE):
                        yield chunk

                return s3_generator(), content_length, content_type
            except Exception as e:
                raise FileNotFoundError(f"Failed to fetch '{s3_key}' from S3 bucket '{self.bucket_name}': {str(e)}")

        # Local mock stream (only if USE_MOCK_S3 is true)
        file_path = LOCAL_MOCK_DIR / s3_key
        if not file_path.exists():
            raise FileNotFoundError(f"Key '{s3_key}' not found in local mock repository.")

        content_length = file_path.stat().st_size

        def local_generator():
            with open(file_path, "rb") as f:
                while chunk := f.read(STREAM_CHUNK_SIZE):
                    yield chunk

        return local_generator(), content_length, content_type


# Singleton S3 client instance
s3_client = S3StreamClient()

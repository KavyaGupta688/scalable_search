from __future__ import annotations

import asyncio
from typing import AsyncGenerator, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError

from ingestion.config import get_settings
from ingestion.schemas.job import JobDescriptor
from ingestion.connectors.base import (
    SourceConnector,
    TransientConnectorError,
    PermanentConnectorError,
)


class S3Connector(SourceConnector):
    """S3 Source Connector implementation."""

    def __init__(
        self,
        endpoint_url: Optional[str],
        bucket: str,
        access_key: str,
        secret_key: str,
        addressing_style: str = "path",
        signature_version: str = "s3v4",
        chunk_size: Optional[int] = None,
        connector_id: Optional[str] = None,
    ):
        self.bucket = bucket
        self.connector_id = connector_id
        settings = get_settings()
        self.chunk_size = chunk_size or settings.worker.chunk_size_bytes
        self.checkpoint_interval = settings.worker.checkpoint_interval_pages

        boto_config = Config(
            s3={"addressing_style": addressing_style},
            signature_version=signature_version,
        )

        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1",
            config=boto_config,
        )

    def _handle_error(self, e: Exception) -> Exception:
        """Map boto3 exceptions to ConnectorError."""
        if isinstance(e, ClientError):
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ["AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch", "NoSuchBucket", "NoSuchKey"]:
                return PermanentConnectorError(f"S3 Permanent Error: {str(e)}")
            return TransientConnectorError(f"S3 Transient Error: {str(e)}")
        if isinstance(e, BotoCoreError):
            return TransientConnectorError(f"S3 Botocore Error: {str(e)}")
        return TransientConnectorError(f"S3 Error: {str(e)}")

    async def test_connection(self) -> bool:
        """Test connectivity to the source. Returns True on success."""
        try:
            await asyncio.to_thread(self.client.list_objects_v2, Bucket=self.bucket, MaxKeys=1)
            return True
        except Exception as e:
            raise self._handle_error(e)

    async def enumerate(self, checkpoint: Optional[str] = None) -> AsyncGenerator[tuple[JobDescriptor, Optional[str]], None]:
        """Yield (job_descriptor, checkpoint_token) pairs."""
        paginator = self.client.get_paginator("list_objects_v2")
        kwargs = {"Bucket": self.bucket}
        if checkpoint:
            kwargs["ContinuationToken"] = checkpoint

        try:
            page_iterator = await asyncio.to_thread(
                lambda: list(paginator.paginate(**kwargs))
            )
        except Exception as e:
            raise self._handle_error(e)

        page_count = 0
        for page in page_iterator:
            page_count += 1
            contents = page.get("Contents", [])
            
            token = None
            if page_count % self.checkpoint_interval == 0:
                token = page.get("NextContinuationToken")

            for idx, obj in enumerate(contents):
                job = JobDescriptor(
                    source_type="S3",
                    connector_id=self.connector_id,
                    source_ref=f"{self.bucket}/{obj['Key']}",
                    provisional_id=obj.get("ETag", "").strip('"'),
                    size_bytes=obj.get("Size", 0),
                    etag=obj.get("ETag", "").strip('"'),
                    bucket=self.bucket,
                    object_key=obj["Key"],
                )
                
                # Only yield the token on the last item of the Nth page
                yield_token = token if idx == len(contents) - 1 else None
                yield job, yield_token

    async def _read_stream(self, body, chunk_size: int) -> AsyncGenerator[bytes, None]:
        while True:
            chunk = await asyncio.to_thread(body.read, chunk_size)
            if not chunk:
                break
            yield chunk

    async def open_stream(self, job: JobDescriptor) -> AsyncGenerator[bytes, None]:
        """Yield byte chunks (8MB each) from the source file."""
        key = job.source_ref.split("/", 1)[1]
        try:
            response = await asyncio.to_thread(self.client.get_object, Bucket=self.bucket, Key=key)
            async for chunk in self._read_stream(response["Body"], self.chunk_size):
                yield chunk
        except Exception as e:
            raise self._handle_error(e)

    async def open_stream_from_offset(self, job: JobDescriptor, offset: int) -> AsyncGenerator[bytes, None]:
        """Resume streaming from a byte offset (for retry with Range requests)."""
        key = job.source_ref.split("/", 1)[1]
        try:
            response = await asyncio.to_thread(
                self.client.get_object,
                Bucket=self.bucket,
                Key=key,
                Range=f"bytes={offset}-"
            )
            async for chunk in self._read_stream(response["Body"], self.chunk_size):
                yield chunk
        except Exception as e:
            raise self._handle_error(e)

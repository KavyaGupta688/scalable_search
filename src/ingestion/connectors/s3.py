from __future__ import annotations

import asyncio
import re
import time
from typing import AsyncGenerator, Optional
from urllib.parse import urlparse

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
from ingestion.monitoring.logging import get_logger
from ingestion.monitoring.metrics import METRICS

logger = get_logger(__name__)


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
        prefix: str = "",
        max_objects: Optional[int] = None,
        page_size: int = 1000,
    ):
        self.bucket = bucket
        self.connector_id = connector_id
        self.prefix = prefix
        self.max_objects = max_objects
        self.page_size = page_size
        settings = get_settings()
        self.chunk_size = chunk_size or settings.worker.chunk_size_bytes
        self.checkpoint_interval = settings.worker.checkpoint_interval_pages

        # AWS requires SigV4 requests to be signed for the bucket's region.
        # Infer it from a regional endpoint; S3-compatible endpoints continue
        # to use the us-east-1-compatible default.
        region_name = "us-east-1"
        if endpoint_url:
            hostname = urlparse(endpoint_url).hostname or ""
            match = re.search(r"(?:^|\.)s3[.-]([a-z0-9-]+)\.amazonaws\.com$", hostname)
            if match:
                region_name = match.group(1)

        boto_config = Config(
            s3={"addressing_style": addressing_style},
            signature_version=signature_version,
            retries={"max_attempts": 8, "mode": "adaptive"},
            connect_timeout=10,
            read_timeout=120,
            max_pool_connections=32,
            tcp_keepalive=True,
        )

        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region_name,
            config=boto_config,
        )
        # Exposed for structured completion logging by the orchestration layer.
        self.last_enumeration_stats: dict[str, float | int | bool] = {
            "pages": 0,
            "objects": 0,
            "list_seconds": 0.0,
            "first_page_seconds": 0.0,
            "limit_reached": False,
        }

    def _handle_error(self, e: Exception) -> Exception:
        """Map boto3 exceptions to ConnectorError."""
        if isinstance(e, ClientError):
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in [
                "AccessDenied",
                "InvalidAccessKeyId",
                "SignatureDoesNotMatch",
                "NoSuchBucket",
                "NoSuchKey",
                "PermanentRedirect",
                "AuthorizationHeaderMalformed",
                "InvalidRegion",
            ]:
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

    async def enumerate(
        self, checkpoint: Optional[str] = None
    ) -> AsyncGenerator[tuple[JobDescriptor, Optional[str]], None]:
        """Yield jobs one ListObjectsV2 page at a time.

        S3 continuation tokens are inherently sequential, so fetching the next
        page concurrently is neither safe nor useful.  The old implementation
        converted the whole paginator to a list, which delayed the first job
        until the complete bucket had been listed and retained every page in
        memory.  This version keeps at most one page (1,000 keys) in memory.

        A checkpoint is yielded after a configurable number of fully produced
        pages.  The orchestrator flushes Kafka before persisting it, so a
        crash can replay at most that many pages; it cannot skip objects.
        """
        continuation_token = checkpoint
        page_count = 0
        objects_yielded = 0
        list_seconds = 0.0
        started_at = time.perf_counter()
        self.last_enumeration_stats = {
            "pages": 0,
            "objects": 0,
            "list_seconds": 0.0,
            "first_page_seconds": 0.0,
            "limit_reached": False,
        }

        while True:
            kwargs = {
                "Bucket": self.bucket,
                "MaxKeys": self.page_size,
            }
            if self.prefix:
                kwargs["Prefix"] = self.prefix
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token

            request_started_at = time.perf_counter()
            try:
                page = await asyncio.to_thread(self.client.list_objects_v2, **kwargs)
            except Exception as e:
                raise self._handle_error(e)
            request_seconds = time.perf_counter() - request_started_at
            list_seconds += request_seconds
            page_count += 1
            METRICS.ENUMERATION_PAGES_TOTAL.labels(source_type="S3").inc()
            METRICS.PROCESSING_DURATION_SECONDS.labels(
                source_type="S3", stage="enumeration_list_page"
            ).observe(request_seconds)

            if page_count == 1:
                self.last_enumeration_stats["first_page_seconds"] = (
                    time.perf_counter() - started_at
                )

            contents = page.get("Contents", [])
            next_token = page.get("NextContinuationToken")

            for index, obj in enumerate(contents):
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
                objects_yielded += 1
                METRICS.ENUMERATION_OBJECTS_TOTAL.labels(source_type="S3").inc()

                # Attach a checkpoint only to the last object of a completed
                # checkpoint interval.  Batching avoids a Kafka flush and RDS
                # transaction for every 1,000-key page while preserving
                # at-least-once recovery.
                is_page_last_object = index == len(contents) - 1
                checkpoint_due = page_count % self.checkpoint_interval == 0
                yield job, next_token if is_page_last_object and checkpoint_due else None

                if self.max_objects is not None and objects_yielded >= self.max_objects:
                    self.last_enumeration_stats.update(
                        pages=page_count,
                        objects=objects_yielded,
                        list_seconds=list_seconds,
                        limit_reached=True,
                    )
                    METRICS.ENUMERATION_LIMIT_REACHED_TOTAL.labels(source_type="S3").inc()
                    logger.info(
                        "S3 enumeration stopped at configured object cap",
                        extra={
                            "connector_id": str(self.connector_id),
                            "prefix": self.prefix,
                            "max_objects": self.max_objects,
                            "pages": page_count,
                        },
                    )
                    return

            self.last_enumeration_stats.update(
                pages=page_count,
                objects=objects_yielded,
                list_seconds=list_seconds,
            )

            # An empty but truncated page is legal. There is no job to carry a
            # checkpoint, so move forward in-memory; the next non-empty page
            # will make the durable checkpoint conservative (a replay only).
            if not page.get("IsTruncated") or not next_token:
                return
            continuation_token = next_token

    async def _read_stream(self, body, chunk_size: int) -> AsyncGenerator[bytes, None]:
        try:
            while True:
                chunk = await asyncio.to_thread(body.read, chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            # Return the HTTP connection to botocore's pool even when a
            # ResponseStreamingError or task cancellation interrupts reading.
            await asyncio.to_thread(body.close)

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

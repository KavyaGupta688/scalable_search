from __future__ import annotations

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
import asyncio
from typing import Any, AsyncGenerator, Iterable

from ingestion.config import get_settings

class MinIOClient:
    def __init__(self):
        settings = get_settings().minio
        self.bucket = settings.bucket
        self.client = boto3.client(
            's3',
            endpoint_url=settings.endpoint_url,
            aws_access_key_id=settings.access_key,
            aws_secret_access_key=settings.secret_key,
            region_name=settings.region,
            config=Config(
                s3={'addressing_style': 'path'},
                signature_version='s3v4',
                retries={'max_attempts': 8, 'mode': 'adaptive'},
                connect_timeout=10,
                read_timeout=120,
                max_pool_connections=32,
                tcp_keepalive=True,
            )
        )
        self.ensure_bucket()
        
    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchBucket", "NotFound"}:
                self.client.create_bucket(Bucket=self.bucket)
                return
            # AccessDenied and connectivity/configuration errors must never be
            # mistaken for an absent bucket.
            raise
            
    async def create_multipart_upload(self, key: str) -> str:
        def _upload():
            return self.client.create_multipart_upload(Bucket=self.bucket, Key=key)
        response = await asyncio.to_thread(_upload)
        return response['UploadId']

    async def put_object(self, key: str, data: bytes, content_type: str) -> str | None:
        """Upload a bounded in-memory object with one S3 request."""
        response = await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return response.get("VersionId")
        
    async def upload_part(self, key: str, upload_id: str, part_number: int, data: bytes) -> str:
        def _upload_part():
            return self.client.upload_part(
                Bucket=self.bucket,
                Key=key,
                PartNumber=part_number,
                UploadId=upload_id,
                Body=data
            )
        response = await asyncio.to_thread(_upload_part)
        return response['ETag']
        
    async def complete_multipart_upload(
        self, key: str, upload_id: str, parts: list[dict[str, Any]]
    ) -> str | None:
        def _complete():
            return self.client.complete_multipart_upload(
                Bucket=self.bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
        response = await asyncio.to_thread(_complete)
        return response.get("VersionId")
        
    async def abort_multipart_upload(self, key: str, upload_id: str) -> None:
        def _abort():
            self.client.abort_multipart_upload(
                Bucket=self.bucket,
                Key=key,
                UploadId=upload_id
            )
        await asyncio.to_thread(_abort)
        
    async def object_exists(self, key: str, version_id: str | None = None) -> bool:
        def _head():
            try:
                params: dict[str, Any] = {"Bucket": self.bucket, "Key": key}
                if version_id:
                    params["VersionId"] = version_id
                self.client.head_object(**params)
                return True
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in {"404", "NoSuchKey", "NotFound"}:
                    return False
                raise
        return await asyncio.to_thread(_head)

    async def head_object(
        self, key: str, version_id: str | None = None
    ) -> dict[str, Any] | None:
        def _head():
            try:
                params: dict[str, Any] = {"Bucket": self.bucket, "Key": key}
                if version_id:
                    params["VersionId"] = version_id
                return self.client.head_object(**params)
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in {"404", "NoSuchKey", "NotFound"}:
                    return None
                raise

        return await asyncio.to_thread(_head)

    async def put_retention_tags(
        self, key: str, tags: dict[str, str], version_id: str | None = None
    ) -> None:
        params: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": key,
            "Tagging": {
                "TagSet": [
                    {"Key": tag_key, "Value": tag_value}
                    for tag_key, tag_value in sorted(tags.items())
                ]
            },
        }
        if version_id:
            params["VersionId"] = version_id
        await asyncio.to_thread(self.client.put_object_tagging, **params)

    async def get_bucket_versioning_status(self) -> str:
        response = await asyncio.to_thread(
            self.client.get_bucket_versioning, Bucket=self.bucket
        )
        return response.get("Status", "Unversioned")

    async def get_object_lock_configuration(self) -> dict[str, Any] | None:
        try:
            response = await asyncio.to_thread(
                self.client.get_object_lock_configuration, Bucket=self.bucket
            )
            return response.get("ObjectLockConfiguration")
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {
                "404",
                "NoSuchObjectLockConfiguration",
                "ObjectLockConfigurationNotFoundError",
            }:
                return None
            raise

    async def apply_managed_lifecycle_rules(
        self, rules: list[dict[str, Any]], managed_rule_ids: Iterable[str]
    ) -> None:
        """Merge our rules without removing unrelated bucket lifecycle rules."""

        managed_ids = set(managed_rule_ids)

        def _apply() -> None:
            try:
                response = self.client.get_bucket_lifecycle_configuration(
                    Bucket=self.bucket
                )
                existing = response.get("Rules", [])
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code not in {
                    "404",
                    "NoSuchLifecycleConfiguration",
                    "NoSuchBucketLifecycle",
                }:
                    raise
                existing = []

            preserved = [rule for rule in existing if rule.get("ID") not in managed_ids]
            merged = preserved + rules
            if len(merged) > 1000:
                raise ValueError("Bucket lifecycle configuration would exceed 1000 rules")
            self.client.put_bucket_lifecycle_configuration(
                Bucket=self.bucket,
                LifecycleConfiguration={"Rules": merged},
            )

        await asyncio.to_thread(_apply)

    async def get_lifecycle_rules(self) -> list[dict[str, Any]]:
        try:
            response = await asyncio.to_thread(
                self.client.get_bucket_lifecycle_configuration, Bucket=self.bucket
            )
            return response.get("Rules", [])
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {
                "404",
                "NoSuchLifecycleConfiguration",
                "NoSuchBucketLifecycle",
            }:
                return []
            raise

    async def list_exact_object_versions(self, key: str) -> list[dict[str, str]]:
        """List every version and delete marker for exactly one object key."""

        def _list() -> list[dict[str, str]]:
            found: list[dict[str, str]] = []
            paginator = self.client.get_paginator("list_object_versions")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=key):
                for item in page.get("Versions", []):
                    if item.get("Key") == key:
                        found.append({"Key": key, "VersionId": item["VersionId"]})
                for item in page.get("DeleteMarkers", []):
                    if item.get("Key") == key:
                        found.append({"Key": key, "VersionId": item["VersionId"]})
            return found

        return await asyncio.to_thread(_list)

    async def object_exists_including_versions(
        self, key: str, versioning_status: str | None = None
    ) -> bool:
        status = versioning_status or await self.get_bucket_versioning_status()
        if status in {"Enabled", "Suspended"}:
            return bool(await self.list_exact_object_versions(key))
        return await self.object_exists(key)

    async def delete_object_and_all_versions(
        self, key: str, versioning_status: str | None = None
    ) -> int:
        """Delete content without ever requesting Object Lock governance bypass."""

        status = versioning_status or await self.get_bucket_versioning_status()
        if status not in {"Enabled", "Suspended"}:
            if not await self.object_exists(key):
                return 0
            await asyncio.to_thread(
                self.client.delete_object, Bucket=self.bucket, Key=key
            )
            return 1

        versions = await self.list_exact_object_versions(key)
        deleted = 0
        for offset in range(0, len(versions), 1000):
            response = await asyncio.to_thread(
                self.client.delete_objects,
                Bucket=self.bucket,
                Delete={"Objects": versions[offset : offset + 1000], "Quiet": False},
            )
            errors = response.get("Errors", [])
            if errors:
                error = errors[0]
                raise ClientError(
                    {
                        "Error": {
                            "Code": error.get("Code", "DeleteFailed"),
                            "Message": error.get("Message", "Version deletion failed"),
                        }
                    },
                    "DeleteObjects",
                )
            deleted += len(response.get("Deleted", []))
        return deleted
            
    async def generate_presigned_url(
        self, key: str, expires_in: int = 3600, version_id: str | None = None
    ) -> str:
        def _generate():
            params: dict[str, str] = {'Bucket': self.bucket, 'Key': key}
            if version_id:
                params['VersionId'] = version_id
            return self.client.generate_presigned_url(
                'get_object',
                Params=params,
                ExpiresIn=expires_in
            )
        return await asyncio.to_thread(_generate)
        
    async def get_object_content(self, key: str) -> bytes:
        """Compatibility helper for small callers; avoid for ingestion paths."""
        def _get():
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return response['Body'].read()
        return await asyncio.to_thread(_get)

    async def open_stream(
        self, key: str, chunk_size: int = 1024 * 1024
    ) -> AsyncGenerator[bytes, None]:
        """Read a destination object without materialising it in memory."""
        response = await asyncio.to_thread(
            self.client.get_object, Bucket=self.bucket, Key=key
        )
        body = response["Body"]
        try:
            while True:
                chunk = await asyncio.to_thread(body.read, chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            await asyncio.to_thread(body.close)

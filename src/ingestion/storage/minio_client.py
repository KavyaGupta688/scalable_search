from __future__ import annotations

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
import asyncio
from typing import Any

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
            config=Config(s3={'addressing_style': 'path'}, signature_version='s3v4')
        )
        self.ensure_bucket()
        
    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)
            
    async def create_multipart_upload(self, key: str) -> str:
        def _upload():
            return self.client.create_multipart_upload(Bucket=self.bucket, Key=key)
        response = await asyncio.to_thread(_upload)
        return response['UploadId']
        
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
        
    async def complete_multipart_upload(self, key: str, upload_id: str, parts: list[dict[str, Any]]) -> None:
        def _complete():
            self.client.complete_multipart_upload(
                Bucket=self.bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
        await asyncio.to_thread(_complete)
        
    async def abort_multipart_upload(self, key: str, upload_id: str) -> None:
        def _abort():
            self.client.abort_multipart_upload(
                Bucket=self.bucket,
                Key=key,
                UploadId=upload_id
            )
        await asyncio.to_thread(_abort)
        
    async def object_exists(self, key: str) -> bool:
        def _head():
            try:
                self.client.head_object(Bucket=self.bucket, Key=key)
                return True
            except ClientError:
                return False
        return await asyncio.to_thread(_head)
            
    async def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        def _generate():
            return self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': key},
                ExpiresIn=expires_in
            )
        return await asyncio.to_thread(_generate)
        
    async def get_object_content(self, key: str) -> bytes:
        def _get():
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return response['Body'].read()
        return await asyncio.to_thread(_get)

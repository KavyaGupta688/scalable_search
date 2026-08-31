from __future__ import annotations

import asyncio
import hashlib
import os
from typing import AsyncGenerator, Optional

from ingestion.config import get_settings
from ingestion.schemas.job import JobDescriptor
from ingestion.connectors.base import (
    SourceConnector,
    TransientConnectorError,
    PermanentConnectorError,
)


class NASConnectorNFS(SourceConnector):
    """NFS Source Connector implementation using OS-level mount."""

    def __init__(
        self,
        mount_path: str,
        chunk_size: Optional[int] = None,
    ):
        self.mount_path = os.path.abspath(mount_path)
        
        settings = get_settings()
        self.chunk_size = chunk_size or settings.worker.chunk_size_bytes
        self.checkpoint_interval = settings.worker.checkpoint_interval_pages

        if not os.path.exists(self.mount_path):
            raise PermanentConnectorError(f"NFS mount path does not exist: {self.mount_path}. Ensure the share is mounted at OS-level.")

    async def test_connection(self) -> bool:
        """Test connectivity to the source. Returns True on success."""
        if not os.path.exists(self.mount_path):
            raise PermanentConnectorError(f"NFS mount disconnected: {self.mount_path}")
        return True

    async def enumerate(self, checkpoint: Optional[str] = None) -> AsyncGenerator[tuple[JobDescriptor, Optional[str]], None]:
        """Yield (job_descriptor, checkpoint_token) pairs."""
        
        def walk_dir():
            return list(os.walk(self.mount_path))
            
        try:
            walker = await asyncio.to_thread(walk_dir)
        except Exception as e:
            raise TransientConnectorError(f"Error enumerating NFS: {str(e)}")

        skip = bool(checkpoint)
        count = 0
        
        for root, dirs, files in walker:
            for file_name in files:
                full_path = os.path.join(root, file_name)
                relative_path = os.path.relpath(full_path, self.mount_path).replace("\\", "/")
                
                if skip:
                    if relative_path == checkpoint:
                        skip = False
                    continue
                
                try:
                    stat = await asyncio.to_thread(os.stat, full_path)
                except Exception as e:
                    continue  # Skip files we can't stat
                
                prov_str = f"{relative_path}:{stat.st_size}:{stat.st_mtime}".encode()
                provisional_id = hashlib.sha256(prov_str).hexdigest()[:16]
                
                job = JobDescriptor(
                    source_type="NAS_NFS",
                    source_ref=relative_path,
                    provisional_id=provisional_id,
                    size_bytes=stat.st_size,
                    metadata={
                        "mtime": stat.st_mtime,
                        "full_path": full_path,
                    }
                )
                
                count += 1
                token = relative_path if count % (self.checkpoint_interval * 100) == 0 else None
                yield job, token

    async def _read_stream(self, file_obj, chunk_size: int) -> AsyncGenerator[bytes, None]:
        try:
            while True:
                chunk = await asyncio.to_thread(file_obj.read, chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            await asyncio.to_thread(file_obj.close)

    async def open_stream(self, job: JobDescriptor) -> AsyncGenerator[bytes, None]:
        """Yield byte chunks from the source file."""
        full_path = os.path.join(self.mount_path, job.source_ref)
        try:
            file_obj = await asyncio.to_thread(open, full_path, "rb")
            async for chunk in self._read_stream(file_obj, self.chunk_size):
                yield chunk
        except FileNotFoundError:
            raise PermanentConnectorError(f"File not found: {full_path}")
        except Exception as e:
            raise TransientConnectorError(f"Error opening NFS file: {str(e)}")

    async def open_stream_from_offset(self, job: JobDescriptor, offset: int) -> AsyncGenerator[bytes, None]:
        """Resume streaming from a byte offset."""
        full_path = os.path.join(self.mount_path, job.source_ref)
        try:
            file_obj = await asyncio.to_thread(open, full_path, "rb")
            await asyncio.to_thread(file_obj.seek, offset)
            async for chunk in self._read_stream(file_obj, self.chunk_size):
                yield chunk
        except FileNotFoundError:
            raise PermanentConnectorError(f"File not found: {full_path}")
        except Exception as e:
            raise TransientConnectorError(f"Error opening NFS file: {str(e)}")

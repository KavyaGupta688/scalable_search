from __future__ import annotations

import asyncio
import hashlib
from typing import AsyncGenerator, Optional

import smbclient
from smbprotocol.exceptions import SMBException, SMBOSError

from ingestion.config import get_settings
from ingestion.schemas.job import JobDescriptor
from ingestion.connectors.base import (
    SourceConnector,
    TransientConnectorError,
    PermanentConnectorError,
)


class NASConnectorSMB(SourceConnector):
    """SMB/CIFS Source Connector implementation using smbprotocol."""

    def __init__(
        self,
        server: str,
        share_name: str,
        username: str,
        password: str,
        domain: Optional[str] = None,
        port: int = 445,
        chunk_size: Optional[int] = None,
        connector_id: Optional[str] = None,
    ):
        self.server = server
        self.share_name = share_name
        self.connector_id = connector_id
        self.base_path = f"\\\\{server}\\{share_name}"
        
        settings = get_settings()
        self.chunk_size = chunk_size or settings.worker.chunk_size_bytes
        self.checkpoint_interval = settings.worker.checkpoint_interval_pages

        try:
            smbclient.register_session(
                server=server,
                username=username,
                password=password,
                port=port,
            )
        except Exception as e:
            raise self._handle_error(e)

    def _handle_error(self, e: Exception) -> Exception:
        """Map smbclient exceptions to ConnectorError."""
        if isinstance(e, SMBOSError):
            if e.ntstatus in [0xC0000022, 0xC000006D]: # STATUS_ACCESS_DENIED, STATUS_LOGON_FAILURE
                return PermanentConnectorError(f"SMB Permission Denied: {str(e)}")
            return TransientConnectorError(f"SMB Transient Error: {str(e)}")
        if isinstance(e, SMBException):
            return TransientConnectorError(f"SMB Error: {str(e)}")
        return TransientConnectorError(f"Unknown SMB Error: {str(e)}")

    async def test_connection(self) -> bool:
        """Test connectivity to the source. Returns True on success."""
        try:
            entries = await asyncio.to_thread(lambda: list(smbclient.scandir(self.base_path)))
            return True
        except Exception as e:
            raise self._handle_error(e)

    async def enumerate(self, checkpoint: Optional[str] = None) -> AsyncGenerator[tuple[JobDescriptor, Optional[str]], None]:
        """Yield (job_descriptor, checkpoint_token) pairs."""
        try:
            walker = await asyncio.to_thread(lambda: list(smbclient.walk(self.base_path)))
        except Exception as e:
            raise self._handle_error(e)

        skip = bool(checkpoint)
        count = 0
        
        for root, dirs, files in walker:
            for file_name in files:
                full_path = f"{root}\\{file_name}"
                relative_path = full_path[len(self.base_path) + 1:].replace("\\", "/")
                
                if skip:
                    if relative_path == checkpoint:
                        skip = False
                    continue
                
                try:
                    stat = await asyncio.to_thread(smbclient.stat, full_path)
                except Exception as e:
                    continue  # Skip files we can't stat
                
                prov_str = f"{relative_path}:{stat.st_size}:{stat.st_mtime}".encode()
                provisional_id = hashlib.sha256(prov_str).hexdigest()[:16]
                
                from datetime import datetime
                mtime_dt = datetime.fromtimestamp(stat.st_mtime)
                
                job = JobDescriptor(
                    source_type="NAS_SMB",
                    connector_id=self.connector_id,
                    source_ref=f"{self.share_name}/{relative_path}",
                    provisional_id=provisional_id,
                    size_bytes=stat.st_size,
                    mount_path=self.base_path,
                    relative_path=relative_path,
                    mtime=mtime_dt,
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
        relative_path = job.source_ref.split("/", 1)[1].replace("/", "\\")
        full_path = f"{self.base_path}\\{relative_path}"
        try:
            file_obj = await asyncio.to_thread(smbclient.open_file, full_path, mode="rb", share_access="r")
            async for chunk in self._read_stream(file_obj, self.chunk_size):
                yield chunk
        except Exception as e:
            raise self._handle_error(e)

    async def open_stream_from_offset(self, job: JobDescriptor, offset: int) -> AsyncGenerator[bytes, None]:
        """Resume streaming from a byte offset."""
        relative_path = job.source_ref.split("/", 1)[1].replace("/", "\\")
        full_path = f"{self.base_path}\\{relative_path}"
        try:
            file_obj = await asyncio.to_thread(smbclient.open_file, full_path, mode="rb", share_access="r")
            await asyncio.to_thread(file_obj.seek, offset)
            async for chunk in self._read_stream(file_obj, self.chunk_size):
                yield chunk
        except Exception as e:
            raise self._handle_error(e)

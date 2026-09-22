from __future__ import annotations

import asyncio
import hashlib
import weakref
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional
from uuid import UUID

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
        connector_id: UUID,
        domain: Optional[str] = None,
        root_path: str = "",
        port: int = 445,
        chunk_size: Optional[int] = None,
        max_files: Optional[int] = None,
    ):
        self.server = server
        self.share_name = share_name
        self.connector_id = connector_id
        self.root_path = root_path.strip("\\/")
        self.base_path = f"\\\\{server}\\{share_name}"
        if self.root_path:
            self.base_path = f"{self.base_path}\\{self.root_path}"
        self.max_files = max_files
        # Never let another connector to the same server reuse this identity.
        self._connection_cache = {}
        self._cleanup = weakref.finalize(self, smbclient.reset_connection_cache, connection_cache=self._connection_cache)
        
        settings = get_settings()
        self.chunk_size = chunk_size or settings.worker.chunk_size_bytes
        self.checkpoint_interval = settings.worker.checkpoint_interval_pages

        try:
            session_username = username
            if domain and username and "\\" not in username and "@" not in username:
                session_username = f"{domain}\\{username}"
            smbclient.register_session(
                server=server,
                username=session_username,
                password=password,
                port=port,
                connection_cache=self._connection_cache,
                connection_timeout=10,
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
            def check():
                entries = smbclient.scandir(self.base_path, connection_cache=self._connection_cache)
                try:
                    next(iter(entries), None)
                finally:
                    entries.close()
            await asyncio.to_thread(check)
            return True
        except Exception as e:
            raise self._handle_error(e)

    async def enumerate(self, checkpoint: Optional[str] = None) -> AsyncGenerator[tuple[JobDescriptor, Optional[str]], None]:
        """Yield (job_descriptor, checkpoint_token) pairs."""
        try:
            walker = await asyncio.to_thread(smbclient.walk, self.base_path, connection_cache=self._connection_cache, follow_symlinks=False, onerror=_raise_walk_error)
        except Exception as e:
            raise self._handle_error(e)

        skip = bool(checkpoint)
        count = 0
        
        while True:
            try:
                walked = await asyncio.to_thread(_next_or_none, walker)
            except Exception as e:
                raise self._handle_error(e)
            if walked is None:
                break

            root, dirs, files = walked
            dirs.sort(key=str.casefold)
            files.sort(key=str.casefold)
            for file_name in files:
                full_path = f"{root}\\{file_name}"
                relative_path = full_path[len(self.base_path) + 1:].replace("\\", "/")
                
                if skip:
                    if relative_path == checkpoint:
                        skip = False
                    continue
                
                try:
                    stat = await asyncio.to_thread(smbclient.stat, full_path, connection_cache=self._connection_cache)
                except Exception as e:
                    raise self._handle_error(e)
                
                prov_str = f"{relative_path}:{stat.st_size}:{stat.st_mtime}".encode()
                provisional_id = hashlib.sha256(prov_str).hexdigest()[:16]
                
                mtime_dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

                source_parts = [self.share_name]
                if self.root_path:
                    source_parts.append(self.root_path.replace("\\", "/"))
                source_parts.append(relative_path)
                
                job = JobDescriptor(
                    source_type="NAS_SMB",
                    connector_id=self.connector_id,
                    source_ref="/".join(source_parts),
                    provisional_id=provisional_id,
                    size_bytes=stat.st_size,
                    mount_path=self.base_path,
                    relative_path=relative_path,
                    mtime=mtime_dt,
                )
                
                count += 1
                token = relative_path if count % (self.checkpoint_interval * 100) == 0 else None
                yield job, token
                if self.max_files is not None and count >= self.max_files:
                    return

        if skip:
            raise PermanentConnectorError(
                f"SMB checkpoint path no longer exists: {checkpoint}. "
                "Clear the connector checkpoint and restart enumeration."
            )

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
        relative_path = (job.relative_path or job.source_ref.split("/", 1)[1]).replace("/", "\\")
        full_path = self._safe_path(relative_path)
        try:
            file_obj = await asyncio.to_thread(smbclient.open_file, full_path, mode="rb", share_access="r", connection_cache=self._connection_cache)
            async for chunk in self._read_stream(file_obj, self.chunk_size):
                yield chunk
        except Exception as e:
            raise self._handle_error(e)

    async def open_stream_from_offset(self, job: JobDescriptor, offset: int) -> AsyncGenerator[bytes, None]:
        """Resume streaming from a byte offset."""
        relative_path = (job.relative_path or job.source_ref.split("/", 1)[1]).replace("/", "\\")
        full_path = self._safe_path(relative_path)
        try:
            file_obj = await asyncio.to_thread(smbclient.open_file, full_path, mode="rb", share_access="r", connection_cache=self._connection_cache)
            await asyncio.to_thread(file_obj.seek, offset)
            async for chunk in self._read_stream(file_obj, self.chunk_size):
                yield chunk
        except Exception as e:
            raise self._handle_error(e)

    def _safe_path(self, relative_path):
        if any(part in ("", ".", "..") or ":" in part for part in relative_path.split("\\")):
            raise PermanentConnectorError("SMB file path must remain inside the configured share folder")
        return f"{self.base_path}\\{relative_path}"


def _next_or_none(iterator):
    """Advance a blocking iterator without leaking StopIteration through a Future."""
    try:
        return next(iterator)
    except StopIteration:
        return None


def _raise_walk_error(error):
    raise error  # Access denied must not become a successful empty scan.

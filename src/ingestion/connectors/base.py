from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional

from ingestion.schemas.job import JobDescriptor


class ConnectorError(Exception):
    """Base exception for all connector errors."""
    pass


class TransientConnectorError(ConnectorError):
    """A retryable connector error (e.g., temporary network failure)."""
    pass


class PermanentConnectorError(ConnectorError):
    """A non-retryable connector error (e.g., auth failure, invalid path)."""
    pass


class SourceConnector(ABC):
    """Base interface for all source connectors."""

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test connectivity to the source. Returns True on success."""
        pass

    @abstractmethod
    async def enumerate(self, checkpoint: Optional[str] = None) -> AsyncGenerator[tuple[JobDescriptor, Optional[str]], None]:
        """Yield (job_descriptor, checkpoint_token) pairs. checkpoint_token is non-None every N pages."""
        pass

    @abstractmethod
    async def open_stream(self, job: JobDescriptor) -> AsyncGenerator[bytes, None]:
        """Yield byte chunks (8MB each) from the source file."""
        pass

    @abstractmethod
    async def open_stream_from_offset(self, job: JobDescriptor, offset: int) -> AsyncGenerator[bytes, None]:
        """Resume streaming from a byte offset (for retry with Range requests)."""
        pass

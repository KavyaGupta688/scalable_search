from __future__ import annotations
import magic

class PermanentProcessingError(Exception):
    """Exception for permanent processing errors, no retry."""
    pass

class TransientProcessingError(Exception):
    """Exception for transient processing errors, retry with backoff."""
    pass

def validate_mime_type(first_chunk: bytes, allowed_mimes: set[str]) -> str:
    detected = magic.from_buffer(first_chunk, mime=True)
    if detected not in allowed_mimes:
        raise PermanentProcessingError(f'Rejected MIME type: {detected}')
    return detected

"""
Zero-Re-Encode Binary JPEG Metadata Injector.

Inserts a standard JPEG COM (Comment: 0xFFFE) / APP1 metadata segment containing
the cryptographic tracking token directly after the SOI marker (0xFFD8) without
touching DCT coefficients, quantization tables, or scan data.

Guarantees:
1. 0% alteration of pixel matrices or entropy-coded image scans.
2. Fast O(1) binary injection without recompression artifacts.
3. Survives standard file renaming.
"""
import struct
from typing import Iterator

JPEG_SOI = b"\xFF\xD8"
COM_MARKER = b"\xFF\xFE"
WATERMARK_PREFIX = "EnterpriseWatermarkToken:"


def build_jpeg_com_segment(token_str: str) -> bytes:
    """
    Constructs a valid JPEG COM (Comment) segment:
    [2 bytes: Marker 0xFFFE] [2 bytes: Length (including length field)] [Payload]
    """
    payload = f"{WATERMARK_PREFIX}{token_str}".encode("utf-8")
    length = len(payload) + 2  # Length includes the 2 bytes of the length field
    return COM_MARKER + struct.pack(">H", length) + payload


def inject_jpeg_watermark_bytes(jpeg_data: bytes, token_str: str) -> bytes:
    """
    Injects the watermark COM segment into raw JPEG bytes directly in memory.
    """
    if not jpeg_data.startswith(JPEG_SOI):
        raise ValueError("Invalid JPEG format: Missing SOI (0xFFD8) marker")

    watermark_segment = build_jpeg_com_segment(token_str)
    
    # Place right after the 2-byte SOI marker (0xFFD8)
    return jpeg_data[:2] + watermark_segment + jpeg_data[2:]


def inject_jpeg_watermark_stream(
    stream_iterator: Iterator[bytes],
    token_str: str
) -> Iterator[bytes]:
    """
    Streams a JPEG while injecting the watermark segment on-the-fly.
    """
    watermark_segment = build_jpeg_com_segment(token_str)
    buffer = bytearray()
    injected = False

    for chunk in stream_iterator:
        if not injected:
            buffer.extend(chunk)
            if len(buffer) >= 2:
                if buffer[:2] == JPEG_SOI:
                    yield bytes(buffer[:2]) + watermark_segment
                    remaining = buffer[2:]
                    if remaining:
                        yield bytes(remaining)
                    buffer.clear()
                    injected = True
                else:
                    # Pass through non-JPEG stream
                    yield bytes(buffer)
                    buffer.clear()
                    injected = True
        else:
            yield chunk

    if buffer:
        yield bytes(buffer)

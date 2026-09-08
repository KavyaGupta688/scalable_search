"""
Unified Multi-Modal Watermarking Injection Dispatcher.

Routes image, audio, video, and general binary assets to their format-specific
zero-distortion injectors based on file extension and binary magic bytes.
"""
from typing import Iterator
from pathlib import Path

from core.injectors.png_injector import (
    PNG_SIGNATURE,
    inject_png_watermark_bytes,
    inject_png_watermark_stream
)
from core.injectors.jpeg_injector import (
    JPEG_SOI,
    inject_jpeg_watermark_bytes,
    inject_jpeg_watermark_stream
)
from core.injectors.audio_injector import (
    inject_audio_watermark_bytes,
    inject_audio_watermark_stream
)
from core.injectors.video_injector import (
    inject_video_watermark_bytes,
    inject_video_watermark_stream
)


IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "jfif", "webp"}
AUDIO_EXTENSIONS = {"wav", "mp3", "flac", "ogg", "m4a", "aac", "wma"}
VIDEO_EXTENSIONS = {"mp4", "mov", "mkv", "webm", "avi", "m4v", "wmv"}


def inject_watermark_bytes(data: bytes, token_str: str, file_identifier: str = "") -> bytes:
    """
    Injects cryptographic watermark into any supported media format in memory.
    """
    ext = Path(file_identifier).suffix.lstrip(".").lower() if file_identifier else ""

    # 1. Images
    if data.startswith(PNG_SIGNATURE) or ext == "png":
        return inject_png_watermark_bytes(data, token_str)
    if data.startswith(JPEG_SOI) or ext in ("jpg", "jpeg", "jfif"):
        return inject_jpeg_watermark_bytes(data, token_str)

    # 2. Audio
    if (
        (data.startswith(b"RIFF") and len(data) > 12 and data[8:12] == b"WAVE")
        or data.startswith(b"fLaC")
        or data.startswith(b"ID3")
        or ext in AUDIO_EXTENSIONS
    ):
        return inject_audio_watermark_bytes(data, token_str, ext=ext)

    # 3. Video
    if (
        (len(data) >= 8 and data[4:8] in (b"ftyp", b"moov", b"wide", b"free"))
        or data.startswith(b"\x1A\x45\xDF\xA3")
        or (data.startswith(b"RIFF") and len(data) > 12 and data[8:12] == b"AVI ")
        or ext in VIDEO_EXTENSIONS
    ):
        return inject_video_watermark_bytes(data, token_str, ext=ext)

    # 4. Fallback: Append metadata segment for generic binary
    return data + f"\n# AGY-WATERMARK-TOKEN: {token_str}\n".encode("utf-8")


def inject_watermark_stream(
    stream_iterator: Iterator[bytes],
    token_str: str,
    file_identifier: str = ""
) -> Iterator[bytes]:
    """
    Injects cryptographic watermark into a streaming generator.
    """
    ext = Path(file_identifier).suffix.lstrip(".").lower() if file_identifier else ""

    if ext == "png":
        return inject_png_watermark_stream(stream_iterator, token_str)
    if ext in ("jpg", "jpeg", "jfif"):
        return inject_jpeg_watermark_stream(stream_iterator, token_str)
    if ext in AUDIO_EXTENSIONS:
        return inject_audio_watermark_stream(stream_iterator, token_str, ext=ext)
    if ext in VIDEO_EXTENSIONS:
        return inject_video_watermark_stream(stream_iterator, token_str, ext=ext)

    # General streaming: buffer opening chunks to detect and inject
    first_chunk = next(stream_iterator, None)
    if not first_chunk:
        return

    buffer = bytearray(first_chunk)
    while len(buffer) < 64 * 1024:
        chunk = next(stream_iterator, None)
        if not chunk:
            break
        buffer.extend(chunk)

    watermarked_head = inject_watermark_bytes(bytes(buffer), token_str, file_identifier=file_identifier)
    yield watermarked_head

    for chunk in stream_iterator:
        yield chunk

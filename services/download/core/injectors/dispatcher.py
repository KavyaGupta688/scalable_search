"""
Unified Multi-Modal Watermarking Injection Dispatcher.

Routes assets to optional signal/native methods and format-specific metadata
injectors. Signal modes intentionally change media samples or coefficients.
"""
from typing import Iterator
from pathlib import Path
from config import JPEG_CODEC_WATERMARK, LOSSLESS_SIGNAL_WATERMARK, NATIVE_AUDIO_WATERMARK, NATIVE_VIDEO_WATERMARK, CODEC_WATERMARK_SECRET

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


def signal_method(file_identifier):
    ext = Path(file_identifier).suffix.lower()
    if JPEG_CODEC_WATERMARK and ext in (".jpg", ".jpeg", ".jfif"):
        return "JPEG-DCT-v1"
    if LOSSLESS_SIGNAL_WATERMARK and ext == ".png":
        return "PNG-DWT-DCT-v1"
    if LOSSLESS_SIGNAL_WATERMARK and ext in (".bmp", ".tif", ".tiff", ".webp"):
        return "Lossless-DWT-DCT-v1"
    if LOSSLESS_SIGNAL_WATERMARK and ext in (".wav", ".flac"):
        return "Audio-STFT-v1"
    if NATIVE_AUDIO_WATERMARK and ext in (".aac", ".m4a"):
        return "AAC-Native-MDCT-v1"
    if NATIVE_AUDIO_WATERMARK and ext == ".mp3":
        return "MP3-Native-MDCT-v1"
    if NATIVE_VIDEO_WATERMARK and ext in (".mp4", ".mov", ".m4v", ".mkv"):
        return "Video-Native-Coefficients-v1"
    return None


def inject_watermark_bytes(data: bytes, token_str: str, file_identifier: str = "") -> bytes:
    """
    Injects cryptographic watermark into any supported media format in memory.
    """
    ext = Path(file_identifier).suffix.lstrip(".").lower() if file_identifier else ""

    if LOSSLESS_SIGNAL_WATERMARK and ext in ("bmp", "tif", "tiff", "webp"):
        from core.signal_lossless import embed_bytes
        from core.crypto import verify_watermark_token
        valid, payload, message = verify_watermark_token(token_str)
        if not valid:
            raise ValueError(message)
        return embed_bytes(data, payload["did"], CODEC_WATERMARK_SECRET)

    if NATIVE_VIDEO_WATERMARK and ext in ("mp4", "m4v", "mov", "mkv"):
        from core.crypto import verify_watermark_token
        from core.native_video import embed_bytes
        valid, payload, message = verify_watermark_token(token_str)
        if not valid:
            raise ValueError(message)
        return embed_bytes(data, payload["did"], CODEC_WATERMARK_SECRET, "matroska" if ext == "mkv" else "mp4")

    if NATIVE_AUDIO_WATERMARK and ext in ("mp3", "aac", "m4a"):
        from core.crypto import verify_watermark_token
        valid, payload, message = verify_watermark_token(token_str)
        if not valid:
            raise ValueError(message)
        if ext == "mp3":
            from core.native_mp3 import embed_bytes
            data = embed_bytes(data, payload["did"], CODEC_WATERMARK_SECRET)
            return inject_audio_watermark_bytes(data, token_str, ext="mp3")
        from core.native_aac import embed_bytes
        # ADTS has no general metadata container. Never prepend an unrelated
        # ID3 or MP4 structure: the authenticated signal ID resolves the audit.
        return embed_bytes(data, payload["did"], CODEC_WATERMARK_SECRET, "ipod" if ext == "m4a" else "adts")

    # 1. Images
    if data.startswith(PNG_SIGNATURE) or ext == "png":
        if LOSSLESS_SIGNAL_WATERMARK:
            from core.crypto import verify_watermark_token
            from core.signal_lossless import embed_bytes
            valid, payload, message = verify_watermark_token(token_str)
            if not valid:
                raise ValueError(message)
            data = embed_bytes(data, payload["did"], CODEC_WATERMARK_SECRET)
        return inject_png_watermark_bytes(data, token_str)
    if data.startswith(JPEG_SOI) or ext in ("jpg", "jpeg", "jfif"):
        if JPEG_CODEC_WATERMARK:
            from core.crypto import verify_watermark_token
            from core.codec_jpeg import embed_bytes
            valid, payload, message = verify_watermark_token(token_str)
            if not valid:
                raise ValueError(message)
            data = embed_bytes(data, payload["did"], CODEC_WATERMARK_SECRET)
        return inject_jpeg_watermark_bytes(data, token_str)

    # 2. Audio
    if (
        (data.startswith(b"RIFF") and len(data) > 12 and data[8:12] == b"WAVE")
        or data.startswith(b"fLaC")
        or data.startswith(b"ID3")
        or ext in AUDIO_EXTENSIONS
    ):
        if LOSSLESS_SIGNAL_WATERMARK and (ext in ("wav", "flac") or data.startswith(b"fLaC") or data[8:12] == b"WAVE"):
            from core.crypto import verify_watermark_token
            from core.signal_audio import embed_bytes
            valid, payload, message = verify_watermark_token(token_str)
            if not valid:
                raise ValueError(message)
            data = embed_bytes(data, payload["did"], CODEC_WATERMARK_SECRET)
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

    if signal_method(file_identifier):
        data = bytearray()
        for chunk in stream_iterator:
            data.extend(chunk)
            if len(data) > 64 * 1024 * 1024:
                raise ValueError("Signal watermark input limit is 64 MiB")
        yield inject_watermark_bytes(bytes(data), token_str, file_identifier)
        return

    if ext == "png":
        yield from inject_png_watermark_stream(stream_iterator, token_str)
        return
    if ext in ("jpg", "jpeg", "jfif"):
        if JPEG_CODEC_WATERMARK:
            data = bytearray()
            for chunk in stream_iterator:
                data.extend(chunk)
                if len(data) > 64 * 1024 * 1024:
                    raise ValueError("Native JPEG watermark limit is 64 MiB")
            yield inject_watermark_bytes(bytes(data), token_str, file_identifier)
        else:
            yield from inject_jpeg_watermark_stream(stream_iterator, token_str)
        return
    if ext in AUDIO_EXTENSIONS:
        yield from inject_audio_watermark_stream(stream_iterator, token_str, ext=ext)
        return
    if ext in VIDEO_EXTENSIONS:
        yield from inject_video_watermark_stream(stream_iterator, token_str, ext=ext)
        return

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

"""
Forensic Multi-Modal Metadata Extractor.

Inspects suspect files across Images (PNG, JPEG), Audio (WAV, MP3, FLAC, OGG),
Video (MP4, MOV, MKV, WEBM, AVI), and generic datasets to extract embedded
cryptographic tracking tokens directly from binary container headers,
even if the file has been renamed or stripped of extension.
"""
import struct
import re
from typing import Optional, Tuple, Union
from pathlib import Path

from core.injectors.png_injector import PNG_SIGNATURE, WATERMARK_KEYWORD as PNG_KW
from core.injectors.jpeg_injector import JPEG_SOI, COM_MARKER, WATERMARK_PREFIX as JPEG_PFX
from core.injectors.audio_injector import WATERMARK_PREFIX as AUDIO_PFX
from core.injectors.video_injector import WATERMARK_PREFIX as VIDEO_PFX


# Regex for HMAC Watermark Signature: AGY-WM-<base64_payload>.<64_hex_hmac>
TOKEN_REGEX = re.compile(rb"AGY-WM-[A-Za-z0-9_=-]+\.[a-f0-9]{64}")


# ==============================================================================
# 1. Image Extractors
# ==============================================================================

def extract_token_from_png(data: bytes) -> Optional[str]:
    """Parses PNG chunks to locate the tEXt watermark chunk."""
    if not data.startswith(PNG_SIGNATURE):
        return None

    offset = 8
    total_len = len(data)

    while offset + 8 <= total_len:
        chunk_len = struct.unpack(">I", data[offset:offset+4])[0]
        chunk_type = data[offset+4:offset+8]
        chunk_data_start = offset + 8
        chunk_data_end = chunk_data_start + chunk_len

        if chunk_data_end + 4 > total_len:
            break

        if chunk_type == b"tEXt":
            chunk_data = data[chunk_data_start:chunk_data_end]
            if b"\x00" in chunk_data:
                keyword, text = chunk_data.split(b"\x00", 1)
                try:
                    kw_str = keyword.decode("latin-1")
                    if kw_str == PNG_KW:
                        return text.decode("utf-8")
                except Exception:
                    pass

        offset = chunk_data_end + 4  # +4 for CRC32

    return None


def extract_token_from_jpeg(data: bytes) -> Optional[str]:
    """Parses JPEG segments to locate the COM or APP1 watermark segment."""
    if not data.startswith(JPEG_SOI):
        return None

    offset = 2
    total_len = len(data)
    prefix_bytes = JPEG_PFX.encode("utf-8")

    while offset + 4 <= total_len:
        if data[offset] != 0xFF:
            offset += 1
            continue

        marker = data[offset:offset+2]
        if marker in (b"\xFF\xD8", b"\xFF\xD9", b"\xFF\x00") or (0xD0 <= marker[1] <= 0xD7):
            offset += 2
            continue

        if offset + 4 > total_len:
            break

        seg_len = struct.unpack(">H", data[offset+2:offset+4])[0]
        seg_data_start = offset + 4
        seg_data_end = offset + 2 + seg_len

        if seg_data_end > total_len:
            break

        if marker == COM_MARKER:
            payload = data[seg_data_start:seg_data_end]
            if payload.startswith(prefix_bytes):
                token = payload[len(prefix_bytes):]
                try:
                    return token.decode("utf-8")
                except Exception:
                    pass

        if marker == b"\xFF\xDA":  # SOS (Start of Scan)
            break

        offset = seg_data_end

    return None


# ==============================================================================
# 2. Audio Extractors
# ==============================================================================

def extract_token_from_wav(data: bytes) -> Optional[str]:
    """Parses WAV RIFF chunks to find LIST-INFO ICMT comment subchunks."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None

    offset = 12
    total_len = len(data)
    prefix_bytes = AUDIO_PFX.encode("utf-8")

    while offset + 8 <= total_len:
        chunk_id = data[offset:offset+4]
        chunk_size = struct.unpack("<I", data[offset+4:offset+8])[0]
        chunk_data_start = offset + 8
        chunk_data_end = chunk_data_start + chunk_size

        if chunk_data_end > total_len:
            chunk_data_end = total_len

        if chunk_id == b"LIST" and chunk_data_start + 4 <= chunk_data_end:
            list_type = data[chunk_data_start:chunk_data_start+4]
            if list_type == b"INFO":
                sub_offset = chunk_data_start + 4
                while sub_offset + 8 <= chunk_data_end:
                    sub_id = data[sub_offset:sub_offset+4]
                    sub_size = struct.unpack("<I", data[sub_offset+4:sub_offset+8])[0]
                    sub_data = data[sub_offset+8 : sub_offset+8+sub_size]

                    if sub_id == b"ICMT" and sub_data.startswith(prefix_bytes):
                        clean_data = sub_data[len(prefix_bytes):].rstrip(b"\x00")
                        try:
                            return clean_data.decode("utf-8")
                        except Exception:
                            pass

                    sub_offset += 8 + sub_size + (1 if sub_size % 2 != 0 else 0)

        # Pad for word alignment
        offset = chunk_data_end + (1 if chunk_size % 2 != 0 else 0)

    return None


def extract_token_from_id3(data: bytes) -> Optional[str]:
    """Parses ID3v2 container tags to locate TXXX/COMM watermark frames."""
    if not data.startswith(b"ID3") or len(data) < 10:
        return None

    raw_size = data[6:10]
    tag_len = (raw_size[0] << 21) | (raw_size[1] << 14) | (raw_size[2] << 7) | raw_size[3]
    tag_data = data[10 : min(len(data), 10 + tag_len)]

    # Search for token inside ID3 metadata block
    match = TOKEN_REGEX.search(tag_data)
    if match:
        try:
            return match.group(0).decode("ascii")
        except Exception:
            pass

    return None


# ==============================================================================
# 3. Video Extractors
# ==============================================================================

def extract_token_from_mp4(data: bytes) -> Optional[str]:
    """Parses ISOBMFF boxes (MP4/MOV) to extract free/udta/meta watermark box."""
    offset = 0
    total_len = len(data)
    prefix_bytes = VIDEO_PFX.encode("utf-8")

    while offset + 8 <= total_len:
        box_len = struct.unpack(">I", data[offset:offset+4])[0]
        box_type = data[offset+4:offset+8]

        if box_len == 0 or box_len == 1:
            break

        box_end = offset + box_len
        if box_end > total_len:
            box_end = total_len

        box_payload = data[offset+8:box_end]
        if box_type in (b"free", b"skip", b"wmrk", b"udta"):
            if box_payload.startswith(prefix_bytes):
                token = box_payload[len(prefix_bytes):]
                try:
                    return token.decode("utf-8")
                except Exception:
                    pass

        if offset > 256 * 1024:
            break

        offset = box_end

    return None


# ==============================================================================
# 4. Master Multi-Modal Extraction Engine
# ==============================================================================

def extract_token_from_bytes(data: bytes) -> Tuple[Optional[str], str]:
    if data.startswith(b"%PDF-"):
        import io
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            token = (reader.metadata or {}).get("/NexusWatermark")
            if token:
                return str(token), "PDF"
        except Exception:
            pass  # Legacy appended metadata may still be found by the generic scan.
    """
    Attempts format-specific header extraction across Images, Audio, Video,
    and generic binaries, followed by a raw cryptographic token scanner.
    Returns: (token_string_or_none, format_detected)
    """
    if len(data) == 0:
        return None, "Empty File"

    # --- 1. Images ---
    if data.startswith(PNG_SIGNATURE):
        token = extract_token_from_png(data)
        return token or _regex_fallback(data), "PNG Image"

    if data.startswith(JPEG_SOI):
        token = extract_token_from_jpeg(data)
        return token or _regex_fallback(data), "JPEG Image"

    # --- 2. Audio ---
    if data.startswith(b"RIFF") and len(data) > 12 and data[8:12] == b"WAVE":
        token = extract_token_from_wav(data)
        return token or _regex_fallback(data), "WAV Audio"

    if data.startswith(b"ID3"):
        token = extract_token_from_id3(data)
        return token or _regex_fallback(data), "MP3 Audio (ID3v2)"

    if data.startswith(b"fLaC"):
        return _regex_fallback(data), "FLAC Lossless Audio"

    if data.startswith(b"OggS"):
        return _regex_fallback(data), "OGG Audio"

    # --- 3. Video ---
    if len(data) >= 8 and data[4:8] in (b"ftyp", b"moov", b"wide", b"free"):
        token = extract_token_from_mp4(data)
        return token or _regex_fallback(data), "MP4 / QuickTime Video"

    if data.startswith(b"\x1A\x45\xDF\xA3"):
        return _regex_fallback(data), "MKV / WebM Video"

    if data.startswith(b"RIFF") and len(data) > 12 and data[8:12] == b"AVI ":
        token = extract_token_from_wav(data)
        return token or _regex_fallback(data), "AVI Video"

    # --- 4. Fallback: Full Header Token Scan ---
    token = _regex_fallback(data)
    if token:
        return token, "Generic Media / Binary"

    return None, "Unknown Format"


def _regex_fallback(data: bytes) -> Optional[str]:
    """Scans the binary buffer for standard HMAC watermark token pattern."""
    match = TOKEN_REGEX.search(data[: 512 * 1024])
    if match:
        try:
            return match.group(0).decode("ascii")
        except Exception:
            pass
    return None


def extract_token_from_file(file_path: Union[str, Path]) -> Tuple[Optional[str], str]:
    """
    Reads a local file and extracts its embedded watermark token.
    """
    path = Path(file_path)
    if not path.exists():
        return None, "File not found"

    with open(path, "rb") as f:
        # Read first 512 KB to inspect container headers
        header_data = f.read(512 * 1024)
        return extract_token_from_bytes(header_data)

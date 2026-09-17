"""Authenticated signal extraction independent of retained metadata."""
from config import CODEC_WATERMARK_SECRET


def inspect_jpeg(data):
    if not data.startswith(b"\xff\xd8"):
        return None
    if not CODEC_WATERMARK_SECRET:
        return {"checked": False, "reason": "Codec extraction secret is not configured"}
    try:
        from core.codec_jpeg import extract_bytes
        download_id = extract_bytes(data, CODEC_WATERMARK_SECRET)
        return {"checked": True, "download_id": download_id, "authenticated": download_id is not None,
                "method": "JPEG-DCT-v1"}
    except (ImportError, ValueError, OSError) as exc:
        return {"checked": False, "reason": str(exc)}


def inspect_signal(data):
    if data.startswith(b"\xff\xd8"):
        return inspect_jpeg(data)
    is_png = data.startswith(b"\x89PNG\r\n\x1a\n")
    is_audio = data.startswith(b"fLaC") or (data.startswith(b"RIFF") and data[8:12] == b"WAVE")
    is_container = data[4:8] == b"ftyp" or data.startswith(b"\x1a\x45\xdf\xa3")
    is_aac = len(data) > 2 and data[0] == 0xff and data[1] & 0xf6 == 0xf0
    is_mp3 = data.startswith(b"ID3") or (len(data) > 2 and data[0] == 0xff and data[1] & 0xe0 == 0xe0 and not is_aac)
    if not (is_png or is_audio or is_aac or is_mp3 or is_container):
        return None
    if not CODEC_WATERMARK_SECRET:
        return {"checked": False, "reason": "Signal extraction secret is not configured"}
    try:
        if is_png:
            from core.signal_png import extract_bytes
            method = "PNG-DWT-DCT-v1"
        elif is_audio:
            from core.signal_audio import extract_bytes
            method = "Audio-STFT-v1"
        elif is_container:
            # MP4/MOV containers may hold AAC audio or H.264/H.265 video.
            # Probe the actual stream, never infer the codec from the extension.
            from core.native_container import extract_bytes
            download_id, method = extract_bytes(data, CODEC_WATERMARK_SECRET)
            return {"checked": True, "download_id": download_id, "authenticated": download_id is not None, "method": method}
        elif is_mp3:
            from core.native_mp3 import extract_bytes
            method = "MP3-Native-MDCT-v1"
        else:
            from core.native_aac import extract_bytes
            method = "AAC-Native-MDCT-v1"
        download_id = extract_bytes(data, CODEC_WATERMARK_SECRET)
        return {"checked": True, "download_id": download_id, "authenticated": download_id is not None, "method": method}
    except (ImportError, ValueError, OSError, RuntimeError) as exc:
        return {"checked": False, "reason": str(exc)}

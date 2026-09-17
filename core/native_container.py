"""Inspect an ISO-BMFF/Matroska container before selecting its native extractor."""
import json
from pathlib import Path
import tempfile

from core.native_aac import _run, _tool


def extract_bytes(data, secret):
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("Native container limit is 64 MiB")
    with tempfile.TemporaryDirectory(prefix="probe-container-") as directory:
        source = Path(directory) / "input.bin"
        source.write_bytes(data)
        info = json.loads(_run([_tool("ffprobe"), "-v", "error", "-show_streams", "-of", "json", str(source)]))
    videos = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    if videos:
        from core.native_video import extract_bytes
        return extract_bytes(data, secret), "Video-Native-Coefficients-v1"
    from core.native_aac import extract_bytes
    return extract_bytes(data, secret), "AAC-Native-MDCT-v1"

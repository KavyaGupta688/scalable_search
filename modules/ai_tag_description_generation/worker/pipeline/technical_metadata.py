"""Technical facts about a media file: pixel size, duration, frame rate.

Search filters on resolution and duration, so these must be persisted with the enrichment.
Vendor metadata cannot supply them: ingestion deliberately drops vendor width/height.
`from_preprocessing` reuses what the live pipeline already measured; `probe` measures a
file directly, for backfilling documents enriched before this was captured.
"""

import json
import subprocess
from typing import Any


def _clean(values: dict[str, Any]) -> dict[str, Any]:
    """Keeps positive numbers only; unknown values are omitted, never stored as 0."""
    cleaned = {}
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if value > 0:
            cleaned[key] = int(value) if key in ("width", "height") else round(float(value), 3)
    return cleaned


def from_preprocessing(prep: Any) -> dict[str, Any]:
    """Facts measured by preprocessing; {} for other modalities or when it failed."""
    data = getattr(prep, "data", None)
    modality = getattr(getattr(prep, "modality", None), "value", None)
    if data is None:
        return {}
    if modality == "image":
        # Orientation-normalized size, i.e. as the photo is displayed.
        image = getattr(data, "original_image", None)
        width, height = image.size if image is not None else getattr(data, "original_size", (None, None))
        return _clean({"width": width, "height": height})
    if modality == "video":
        width, height = getattr(data, "resolution", (None, None))
        return _clean({
            "width": width,
            "height": height,
            "duration": getattr(data, "duration_seconds", None),
            "fps": getattr(data, "fps", None),
        })
    if modality == "audio":
        return _clean({"duration": getattr(data, "duration_seconds", None)})
    return {}


def _ffprobe(path: str) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path],
        capture_output=True, text=True, check=True, timeout=120,
    )
    return json.loads(result.stdout)


def _fps(stream: dict) -> float:
    try:
        numerator, denominator = str(stream.get("r_frame_rate", "0/1")).split("/")
        return float(numerator) / float(denominator) if float(denominator) else 0.0
    except ValueError:
        return 0.0


def probe(path: str, mime_type: str) -> dict[str, Any]:
    """Measures a file without running the enrichment pipeline."""
    if mime_type.startswith("image/"):
        from PIL import Image

        with Image.open(path) as image:
            width, height = image.size
            # EXIF orientations 5-8 store the photo rotated by 90 degrees.
            if image.getexif().get(274, 1) in (5, 6, 7, 8):
                width, height = height, width
        return _clean({"width": width, "height": height})
    if mime_type.startswith(("video/", "audio/")):
        info = _ffprobe(path)
        duration = float(info.get("format", {}).get("duration") or 0)
        video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
        if mime_type.startswith("video/") and video:
            return _clean({
                "width": video.get("width"),
                "height": video.get("height"),
                "duration": duration,
                "fps": _fps(video),
            })
        return _clean({"duration": duration})
    return {}

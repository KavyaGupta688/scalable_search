# worker/pipeline/video_processor.py
"""
Layer 5 - Video Processor.

Extracts keyframes at fixed intervals via ffmpeg (not every frame, not
scene-detection - deliberately simple for MVP GPU budget), generates a
thumbnail, and pulls basic video metadata via ffprobe.
"""

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


# One frame every N seconds - tune based on typical video length in your
# dataset. 5s is a reasonable default for short clips; longer videos may
# want a larger interval to keep frame count (and GPU cost) manageable.
DEFAULT_KEYFRAME_INTERVAL_SECONDS = 5
MAX_KEYFRAMES = 20  # hard cap so a very long video doesn't explode processing cost


@dataclass
class ProcessedVideo:
    keyframes: list[Image.Image]
    thumbnail: Image.Image
    duration_seconds: float
    resolution: tuple[int, int]
    fps: float


def process_video(
    file_path: str,
    interval_seconds: int = DEFAULT_KEYFRAME_INTERVAL_SECONDS,
) -> ProcessedVideo:
    metadata = _probe_video(file_path)
    duration = metadata["duration_seconds"]

    # Don't request more keyframes than the video's length reasonably supports.
    interval = _adjust_interval_for_cap(duration, interval_seconds)

    with tempfile.TemporaryDirectory() as tmp_dir:
        frame_paths = _extract_keyframes(file_path, tmp_dir, interval)
        keyframes = [Image.open(p).convert("RGB") for p in frame_paths]

    thumbnail = _generate_thumbnail(file_path)

    return ProcessedVideo(
        keyframes=keyframes,
        thumbnail=thumbnail,
        duration_seconds=duration,
        resolution=metadata["resolution"],
        fps=metadata["fps"],
    )


def _probe_video(file_path: str) -> dict:
    """Uses ffprobe (ships with ffmpeg) to read video metadata without decoding frames."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", file_path,
        ],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(result.stdout)

    video_stream = next(s for s in info["streams"] if s["codec_type"] == "video")

    duration = float(info["format"].get("duration", 0))
    width = int(video_stream["width"])
    height = int(video_stream["height"])

    # fps is often given as a fraction string like "30000/1001"
    fps_raw = video_stream.get("r_frame_rate", "0/1")
    num, denom = fps_raw.split("/")
    fps = float(num) / float(denom) if float(denom) != 0 else 0.0

    return {"duration_seconds": duration, "resolution": (width, height), "fps": fps}


def _adjust_interval_for_cap(duration: float, interval_seconds: int) -> int:
    estimated_frames = duration / interval_seconds
    if estimated_frames <= MAX_KEYFRAMES:
        return interval_seconds
    # Stretch the interval so total frames stays under the cap
    return max(1, int(duration / MAX_KEYFRAMES))


def _extract_keyframes(file_path: str, output_dir: str, interval_seconds: int) -> list[str]:
    output_pattern = str(Path(output_dir) / "frame_%03d.jpg")
    subprocess.run(
        [
            "ffmpeg", "-i", file_path,
            "-vf", f"fps=1/{interval_seconds}",
            "-vsync", "vfr",
            output_pattern,
        ],
        capture_output=True, check=True,
    )
    return sorted(str(p) for p in Path(output_dir).glob("frame_*.jpg"))


def _generate_thumbnail(file_path: str, at_seconds: float = 1.0) -> Image.Image:
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        subprocess.run(
            [
                "ffmpeg", "-ss", str(at_seconds), "-i", file_path,
                "-frames:v", "1", "-y", tmp.name,
            ],
            capture_output=True, check=True,
        )
        return Image.open(tmp.name).convert("RGB")


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "sample.mp4"
    result = process_video(path)

    print(f"Duration: {result.duration_seconds:.1f}s")
    print(f"Resolution: {result.resolution}")
    print(f"FPS: {result.fps:.1f}")
    print(f"Keyframes extracted: {len(result.keyframes)}")

    for i, frame in enumerate(result.keyframes):
        frame.save(f"keyframe_{i:03d}.jpg")
    result.thumbnail.save("thumbnail.jpg")
    print("Saved keyframes + thumbnail for visual check")
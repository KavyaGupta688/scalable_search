# worker/pipeline/video_processor.py
"""
Layer 5 - Video Processor.

Extracts bounded temporal keyframes via ffmpeg, chooses a representative
middle frame, extracts audio, and reads video metadata via ffprobe.
"""

import json
import math
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
import numpy as np

from modules.ai_tag_description_generation.worker.pipeline.audio_processor import process_audio


# One frame every N seconds - tune based on typical video length in your
# dataset. 5s is a reasonable default for short clips; longer videos may
# want a larger interval to keep frame count (and GPU cost) manageable.
DEFAULT_KEYFRAME_INTERVAL_SECONDS = 2
SHORT_VIDEO_KEYFRAME_INTERVAL_SECONDS = 1
SHORT_VIDEO_CUTOFF_SECONDS = 30
MAX_KEYFRAMES = 20  # hard cap so a very long video doesn't explode processing cost


@dataclass
class ProcessedVideo:
    keyframes: list[Image.Image]
    thumbnail: Image.Image
    duration_seconds: float
    resolution: tuple[int, int]
    fps: float
    has_audio: bool
    audio_waveform: np.ndarray | None


def process_video(
    file_path: str,
    interval_seconds: int = DEFAULT_KEYFRAME_INTERVAL_SECONDS,
) -> ProcessedVideo:
    metadata = _probe_video(file_path)
    duration = metadata["duration_seconds"]

    # Don't request more keyframes than the video's length reasonably supports.
    requested_interval = (
        SHORT_VIDEO_KEYFRAME_INTERVAL_SECONDS
        if interval_seconds == DEFAULT_KEYFRAME_INTERVAL_SECONDS and duration <= SHORT_VIDEO_CUTOFF_SECONDS
        else interval_seconds
    )
    interval = _adjust_interval_for_cap(duration, requested_interval)

    with tempfile.TemporaryDirectory() as tmp_dir:
        frame_paths = _extract_keyframes(file_path, tmp_dir, interval)
        keyframes = [Image.open(p).convert("RGB") for p in frame_paths]

    if not keyframes:
        raise ValueError("Video did not yield any decodable frames")

    # A middle frame is generally more representative than the previous
    # hard-coded one-second thumbnail and requires no extra decode pass.
    thumbnail = keyframes[len(keyframes) // 2].copy()
    audio_waveform = _extract_audio_waveform(file_path) if metadata["has_audio"] else None

    return ProcessedVideo(
        keyframes=keyframes,
        thumbnail=thumbnail,
        duration_seconds=duration,
        resolution=metadata["resolution"],
        fps=metadata["fps"],
        has_audio=metadata["has_audio"],
        audio_waveform=audio_waveform,
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

    video_stream = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if video_stream is None:
        raise ValueError(f"No video stream found in '{file_path}'")

    duration = float(info["format"].get("duration", 0))
    width = int(video_stream["width"])
    height = int(video_stream["height"])

    # fps is often given as a fraction string like "30000/1001"
    fps_raw = video_stream.get("r_frame_rate", "0/1")
    num, denom = fps_raw.split("/")
    fps = float(num) / float(denom) if float(denom) != 0 else 0.0

    has_audio = any(stream.get("codec_type") == "audio" for stream in info.get("streams", []))
    return {
        "duration_seconds": duration,
        "resolution": (width, height),
        "fps": fps,
        "has_audio": has_audio,
    }


def _adjust_interval_for_cap(duration: float, interval_seconds: int) -> int:
    if interval_seconds <= 0:
        raise ValueError("Keyframe interval must be greater than zero")
    estimated_frames = duration / interval_seconds
    if estimated_frames <= MAX_KEYFRAMES:
        return interval_seconds
    # Stretch the interval so total frames stays under the cap
    return max(1, math.ceil(duration / MAX_KEYFRAMES))


def _extract_audio_waveform(file_path: str) -> np.ndarray | None:
    """Extract a 16 kHz mono track; return None when the video has no audio."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        audio_path = tmp.name
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", file_path, "-vn",
                "-ac", "1", "-ar", "16000", audio_path,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg could not extract the video audio track: {result.stderr.strip()}")
        return process_audio(audio_path).waveform
    finally:
        Path(audio_path).unlink(missing_ok=True)


def _extract_keyframes(file_path: str, output_dir: str, interval_seconds: int) -> list[str]:
    output_pattern = str(Path(output_dir) / "frame_%03d.jpg")
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", file_path,
                "-vf", f"fps=1/{interval_seconds}",
                "-an", "-q:v", "2", "-fps_mode", "vfr", output_pattern,
            ],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"ffmpeg could not extract keyframes from '{file_path}':\n{exc.stderr.strip()}"
        ) from exc
    return sorted(str(p) for p in Path(output_dir).glob("frame_*.jpg"))


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

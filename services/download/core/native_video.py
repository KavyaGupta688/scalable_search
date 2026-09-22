"""Experimental all-intra native H.264/H.265 coefficient watermarking.

Native quantized coefficients are changed before the encoder reconstructs its
prediction reference. Decoder hooks read coefficients before inverse transform.
The all-intra restriction avoids unvalidated inter-frame prediction behavior.
"""
from fractions import Fraction
import json
import os
from pathlib import Path
import struct
import tempfile

import numpy as np

from core.native_aac import ROOT, NATIVE_ROOT, _run, _tool
from core.signal_payload import BIT_COUNT, encode, decode, positions


def _probe(path):
    info = json.loads(_run([_tool("ffprobe"), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
    videos = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    audios = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    if len(videos) != 1 or len(audios) > 1:
        raise ValueError("Native video requires one video stream and at most one audio stream")
    video = videos[0]
    codec = video.get("codec_name")
    if codec not in ("h264", "hevc") or video.get("pix_fmt") != "yuv420p":
        raise ValueError("Native video v1 supports only 8-bit YUV420 H.264 and H.265")
    width, height = int(video["width"]), int(video["height"])
    if width % 2 or height % 2 or width * height > 1920 * 1080:
        raise ValueError("Experimental native video limit is 1920x1080 pixels with even dimensions")
    try:
        fps = Fraction(video.get("avg_frame_rate", "0/1"))
        nominal = Fraction(video.get("r_frame_rate", "0/1"))
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("Video frame rate is unknown or invalid") from exc
    if fps != nominal or not 0 < fps <= 30:
        raise ValueError("Native video v1 requires constant frame rate at no more than 30 fps")
    duration = float(info.get("format", {}).get("duration", 0))
    if not 0 < duration <= 12:
        raise ValueError("Experimental native video duration limit is 12 seconds")
    return codec, width, height, str(fps), bool(audios)


def _config(path, codec, secret, download_id=None):
    domain = codec + "-native-coeff-v1"
    mapping = positions(BIT_COUNT, BIT_COUNT, secret, domain + "-map")
    bits = encode(download_id, secret, domain) if download_id else np.zeros(BIT_COUNT, dtype=np.uint8)
    path.write_bytes(b"VWM1" + bytes(bits) + struct.pack("<280H", *mapping))
    return mapping


def _env(config, embed=False, report=None):
    env = dict(os.environ)
    for prefix in ("AAC", "MP3", "VIDEO"):
        for suffix in ("CONFIG", "EMBED", "EXTRACT"):
            env.pop(f"AGY_{prefix}_{suffix}", None)
    env["AGY_VIDEO_CONFIG"] = str(config)
    if embed:
        env["AGY_VIDEO_EMBED"] = "1"
    if report:
        env["AGY_VIDEO_EXTRACT"] = str(report)
    return env


def _recover(path, tmp, codec, secret):
    config, report = tmp / "extract-video.cfg", tmp / "video-coefficients.txt"
    mapping = _config(config, codec, secret)
    _run([_tool("ffmpeg"), "-v", "error", "-threads", "1", "-i", str(path), "-map", "0:v:0",
          "-an", "-c:v", "rawvideo", "-f", "null", "-"], env=_env(config, report=report))
    if not report.exists():
        raise ValueError("No supported native video coefficient carriers were found")
    zeros, ones = np.zeros(BIT_COUNT), np.zeros(BIT_COUNT)
    for line in report.read_text().splitlines():
        index, zero, one = (int(v) for v in line.split())
        if 0 <= index < BIT_COUNT:
            zeros[index] += zero
            ones[index] += one
    if np.any(zeros + ones < 3) or np.any(zeros == ones):
        return None
    observed = ones > zeros
    # Scan a complete payload period to tolerate a whole-frame index offset.
    for offset in range(BIT_COUNT):
        bits = np.zeros(BIT_COUNT, dtype=np.uint8)
        for i in range(BIT_COUNT):
            bits[mapping[(i + offset) % BIT_COUNT]] = observed[i]
        result = decode(bits, secret, codec + "-native-coeff-v1")
        if result:
            return result
    return None


def embed_bytes(data, download_id, secret, container="mp4"):
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("Native video input limit is 64 MiB")
    if container not in ("mp4", "matroska"):
        raise ValueError("Native video output must use MP4 or Matroska")
    with tempfile.TemporaryDirectory(prefix="native-video-") as directory:
        tmp = Path(directory)
        source, raw, elementary, output, config = (tmp / p for p in ("input.bin", "frames.yuv", "coded.bin", "output.bin", "embed-video.cfg"))
        source.write_bytes(data)
        codec, width, height, fps, has_audio = _probe(source)
        _config(config, codec, secret, download_id)
        _run([_tool("ffmpeg"), "-v", "error", "-i", str(source), "-map", "0:v:0", "-an", "-pix_fmt", "yuv420p",
              "-c:v", "rawvideo", "-f", "rawvideo", str(raw)])
        if codec == "h264":
            encoder = NATIVE_ROOT / "x264/x264"
            command = [str(encoder), "--demuxer", "raw", "--input-csp", "i420", "--input-res", f"{width}x{height}",
                       "--fps", fps, "--threads", "1", "--keyint", "1", "--bframes", "0", "--qp", "18",
                       "--partitions", "none", "--no-8x8dct", "--trellis", "0", "--no-dct-decimate", "--no-psy",
                       "--output", str(elementary), str(raw)]
        else:
            encoder = NATIVE_ROOT / "x265-build/x265"
            command = [str(encoder), "--input", str(raw), "--input-res", f"{width}x{height}", "--fps", fps,
                       "--input-csp", "i420", "--input-depth", "8", "--frame-threads", "1", "--pools", "none", "--no-wpp",
                       "--keyint", "1", "--bframes", "0", "--qp", "18", "--ctu", "16", "--max-tu-size", "16",
                       "--rdoq-level", "0", "--no-signhide", "--no-tskip", "--no-psy-rd", "--no-psy-rdoq",
                       "--output", str(elementary)]
        if not encoder.is_file():
            raise RuntimeError(f"Native {codec} encoder is not built; run scripts/build_native_video.py")
        _run(command, env=_env(config, embed=True))
        _run([_tool("ffmpeg"), "-v", "error", "-fflags", "+genpts", "-r", fps, "-f", "h264" if codec == "h264" else "hevc",
              "-i", str(elementary), "-i", str(source), "-map", "0:v:0", "-map", "1:a:0?", "-c", "copy",
              "-map_metadata", "-1", "-f", container, str(output)])
        if output.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("All-intra output exceeds the 64 MiB forensic limit")
        if _recover(output, tmp, codec, secret) != download_id.lower():
            raise ValueError("Native video watermark recovery failed; no output delivered")
        return output.read_bytes()


def extract_bytes(data, secret):
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("Native video input limit is 64 MiB")
    with tempfile.TemporaryDirectory(prefix="native-video-extract-") as directory:
        tmp = Path(directory)
        source = tmp / "input.bin"
        source.write_bytes(data)
        codec, _, _, _, _ = _probe(source)
        return _recover(source, tmp, codec, secret)

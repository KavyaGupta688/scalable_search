from pathlib import Path
import json

import numpy as np

import imageio_ffmpeg
import pytest

from core import native_video, native_aac

SECRET = "native-video-development-secret-" * 3
ID = "35b63f71-74d5-45dc-bdd7-7b5a00d227e9"


@pytest.mark.parametrize("codec", ["h264", "hevc"])
def test_native_video_coefficients(codec, tmp_path):
    encoder = native_video.ROOT / ("work/native/x264/x264" if codec == "h264" else "work/native/x265-build/x265")
    if not encoder.exists():
        pytest.skip("Native encoder build required")
    source = tmp_path / "input.mp4"
    native_aac._run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=192x192:rate=10:duration=3",
                     "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=48000:duration=3",
                     "-c:v", "libx264" if codec == "h264" else "libx265", "-c:a", "aac", "-pix_fmt", "yuv420p", "-threads", "1", str(source)])
    marked = native_video.embed_bytes(source.read_bytes(), ID, SECRET)
    assert native_video.extract_bytes(marked, SECRET) == ID
    assert native_video.extract_bytes(marked, SECRET + "wrong") is None
    stripped = tmp_path / "stripped.mp4"
    marked_path = tmp_path / "marked.mp4"
    marked_path.write_bytes(marked)
    def decoded(path):
        raw = native_aac._run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-xerror", "-err_detect", "explode",
                              "-i", str(path), "-map", "0:v:0", "-pix_fmt", "yuv420p", "-f", "rawvideo", "-"])
        return np.frombuffer(raw, dtype=np.uint8)
    before, after = decoded(source), decoded(marked_path)
    assert before.shape == after.shape
    mse = np.mean((before.astype(float) - after) ** 2)
    psnr = 10 * np.log10(255 ** 2 / mse)
    assert psnr > 30, f"Video PSNR: {psnr:.2f} dB"
    def audio_hashes(path):
        report = native_aac._run([native_aac._tool("ffprobe"), "-v", "error", "-select_streams", "a:0",
                                  "-show_packets", "-show_data_hash", "sha256", "-of", "json", str(path)])
        return [p["data_hash"] for p in json.loads(report)["packets"]]
    assert audio_hashes(source) == audio_hashes(marked_path)
    native_aac._run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", str(marked_path), "-map_metadata", "-1",
                     "-c", "copy", str(stripped)])
    assert native_video.extract_bytes(stripped.read_bytes(), SECRET) == ID
    from core.codec_forensics import inspect_signal
    from unittest.mock import patch
    with patch("core.codec_forensics.CODEC_WATERMARK_SECRET", SECRET):
        assert inspect_signal(stripped.read_bytes())["authenticated"]

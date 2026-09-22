import io
import sys
import types
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import pytest
import soundfile as sf
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.native_aac import NATIVE_ROOT, _run

SECRET = "native-gateway-test-secret-" * 3


@pytest.mark.parametrize("kind", ["mp3", "aac", "m4a", "h264", "hevc"])
def test_native_download_and_inspect(kind, monkeypatch, tmp_path):
    if not (NATIVE_ROOT / "ffmpeg-7.1/ffmpeg").exists():
        pytest.skip("Native builds required")
    binary = imageio_ffmpeg.get_ffmpeg_exe()
    ext = "mp4" if kind in ("h264", "hevc") else kind
    source = tmp_path / ("source." + ext)
    if kind in ("h264", "hevc"):
        _run([binary, "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=192x192:rate=10:duration=3",
              "-c:v", "libx264" if kind == "h264" else "libx265", "-threads", "1", str(source)])
    else:
        rate = 44100
        t = np.arange(rate * 12) / rate
        samples = 0.15 * np.sin(2 * np.pi * 440 * t) + 0.035 * np.random.default_rng(53).normal(size=len(t))
        wave = tmp_path / "source.wav"
        sf.write(wave, samples, rate, subtype="PCM_16")
        _run([binary, "-v", "error", "-i", str(wave), "-c:a", "libmp3lame" if kind == "mp3" else "aac",
              "-b:a", "192k", str(source)])
    from core.injectors import dispatcher
    from core import codec_forensics
    monkeypatch.setattr(dispatcher, "NATIVE_AUDIO_WATERMARK", True)
    monkeypatch.setattr(dispatcher, "NATIVE_VIDEO_WATERMARK", True)
    monkeypatch.setattr(dispatcher, "CODEC_WATERMARK_SECRET", SECRET)
    monkeypatch.setattr(codec_forensics, "CODEC_WATERMARK_SECRET", SECRET)
    records = {}
    def record(**kwargs):
        records[kwargs["download_id"]] = kwargs
        return True
    db = types.SimpleNamespace(record_download=record, find_by_download_id=records.get)
    data = source.read_bytes()
    s3 = types.SimpleNamespace(get_file_stream=lambda key: (iter([data]), len(data), "application/octet-stream"))
    monkeypatch.setitem(sys.modules, "database.db", types.SimpleNamespace(db=db))
    monkeypatch.setitem(sys.modules, "core.s3_client", types.SimpleNamespace(s3_client=s3))
    import api.routes as routes
    monkeypatch.setattr(routes, "db", db)
    monkeypatch.setattr(routes, "s3_client", s3)
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    with TestClient(app) as client:
        response = client.get("/api/download", params={"s3_key": "source." + ext})
        assert response.status_code == 200, response.text[:500]
        report = client.post("/api/forensic/verify", files={"file": ("renamed.bin", response.content)})
        assert report.status_code == 200
        body = report.json()
        assert body["signal_watermark"]["authenticated"]
        assert body["decoded_payload"]["did"] == response.headers["x-watermark-download-id"]
        assert body["forensic_audit_trail"]["s3_key"] == "source." + ext

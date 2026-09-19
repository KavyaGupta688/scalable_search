import io
import sys
import types
import zipfile

import numpy as np
from PIL import Image
import pytest
import soundfile as sf
from fastapi import FastAPI
from fastapi.testclient import TestClient

SECRET = "signal-gateway-test-secret-" * 3


def source(ext):
    buffer = io.BytesIO()
    if ext == "png":
        Image.fromarray(np.random.default_rng(17).integers(20, 230, (512, 512, 3), dtype=np.uint8)).save(buffer, "PNG")
    else:
        audio = np.random.default_rng(17).normal(0, 0.1, 44100 * 6)
        sf.write(buffer, audio, 44100, format=ext.upper(), subtype="PCM_24")
    return buffer.getvalue()


def remove_metadata(data, ext):
    buffer = io.BytesIO()
    if ext == "png":
        Image.fromarray(np.asarray(Image.open(io.BytesIO(data)))).save(buffer, "PNG")
    else:
        audio, rate = sf.read(io.BytesIO(data))
        sf.write(buffer, audio, rate, format=ext.upper(), subtype="PCM_24")
    return buffer.getvalue()


@pytest.mark.parametrize("ext", ["png", "wav", "flac"])
def test_gateway_and_worker(ext, monkeypatch, tmp_path):
    from core.injectors import dispatcher
    from core import codec_forensics
    monkeypatch.setattr(dispatcher, "LOSSLESS_SIGNAL_WATERMARK", True)
    monkeypatch.setattr(dispatcher, "CODEC_WATERMARK_SECRET", SECRET)
    monkeypatch.setattr(codec_forensics, "CODEC_WATERMARK_SECRET", SECRET)
    records, progress = {}, []
    def record(**kwargs):
        records[kwargs["download_id"]] = kwargs
        return True
    db = types.SimpleNamespace(record_download=record, find_by_download_id=records.get,
                               update_job_progress=lambda *a, **kw: progress.append(kw))
    data = source(ext)
    s3 = types.SimpleNamespace(get_file_stream=lambda key: (iter([data]), len(data), "application/octet-stream"))
    monkeypatch.setitem(sys.modules, "database.db", types.SimpleNamespace(db=db))
    monkeypatch.setitem(sys.modules, "core.s3_client", types.SimpleNamespace(s3_client=s3))
    import api.routes as routes
    import core.tasks as tasks
    for module in (routes, tasks):
        monkeypatch.setattr(module, "db", db)
        monkeypatch.setattr(module, "s3_client", s3)
    monkeypatch.setattr(routes, "LOSSLESS_SIGNAL_WATERMARK", True)
    monkeypatch.setattr(tasks, "ASYNC_STORAGE_DIR", tmp_path)
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    key = "test." + ext
    with TestClient(app) as client:
        response = client.get("/api/download", params={"s3_key": key})
        assert response.status_code == 200, response.text[:300]
        clean = remove_metadata(response.content, ext)
        from core.injectors.extractor import extract_token_from_bytes
        assert extract_token_from_bytes(clean)[0] is None
        report = client.post("/api/forensic/verify", files={"file": ("renamed.bin", clean)}).json()
        assert report["signal_watermark"]["authenticated"]
        assert report["decoded_payload"]["did"] == response.headers["x-watermark-download-id"]
        assert report["forensic_audit_trail"]["s3_key"] == key
    # Exercise the actual Celery task body without a Redis server.
    result = tasks.process_async_watermarked_package.run("test-job", [key], "user", "user@example.com")
    assert result["status"] == "COMPLETED"
    with zipfile.ZipFile(tmp_path / result["filename"]) as archive:
        clean = remove_metadata(archive.read(key), ext)
    assert codec_forensics.inspect_signal(clean)["authenticated"]

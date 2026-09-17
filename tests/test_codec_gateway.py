"""Isolated API tests: no real S3, Redis or audit database."""
import io
import sys
import types
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from core.crypto import create_tracking_payload, generate_watermark_token
from core.injectors.jpeg_injector import inject_jpeg_watermark_bytes
from core.injectors.extractor import extract_token_from_bytes
from core.codec_jpeg import embed_bytes, extract_bytes

SECRET = "gateway-test-private-secret-" * 3


def strip_metadata(data):
    """Remove APPn/COM segments, preserving the entropy-coded scan verbatim."""
    output = bytearray(data[:2])
    offset = 2
    while offset < len(data):
        assert data[offset] == 255
        marker = data[offset + 1]
        if marker in (0xDA, 0xD9):
            output.extend(data[offset:])
            break
        length = int.from_bytes(data[offset + 2:offset + 4], "big")
        end = offset + 2 + length
        if not (0xE0 <= marker <= 0xEF or marker == 0xFE):
            output.extend(data[offset:end])
        offset = end
    return bytes(output)


def jpeg_bytes(size=(320, 320)):
    buffer = io.BytesIO()
    Image.new("RGB", size, (80, 130, 170)).save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


def test_metadata_removal():
    payload = create_tracking_payload("test-user", "test@example.com", "file.jpg")
    token = generate_watermark_token(payload)
    marked = inject_jpeg_watermark_bytes(embed_bytes(jpeg_bytes(), payload["did"], SECRET), token)
    stripped = strip_metadata(marked)
    assert extract_token_from_bytes(stripped)[0] is None
    assert extract_bytes(stripped, SECRET) == payload["did"]
    Image.open(io.BytesIO(stripped)).load()


def test_download_and_forensic_roundtrip(monkeypatch):
    import core.injectors.dispatcher as dispatcher
    import core.codec_forensics as forensics
    monkeypatch.setattr(dispatcher, "JPEG_CODEC_WATERMARK", True)
    monkeypatch.setattr(dispatcher, "CODEC_WATERMARK_SECRET", SECRET)
    monkeypatch.setattr(forensics, "CODEC_WATERMARK_SECRET", SECRET)
    records = {}
    def record(**kwargs):
        records[kwargs["download_id"]] = kwargs
        return True
    db = types.SimpleNamespace(record_download=record, find_by_download_id=records.get)
    raw = jpeg_bytes()
    s3 = types.SimpleNamespace(get_file_stream=lambda key: (iter([raw]), len(raw), "image/jpeg"))
    monkeypatch.setitem(sys.modules, "core.s3_client", types.SimpleNamespace(s3_client=s3))
    monkeypatch.setitem(sys.modules, "database.db", types.SimpleNamespace(db=db))
    import api.routes as routes
    monkeypatch.setattr(routes, "JPEG_CODEC_WATERMARK", True)
    monkeypatch.setattr(routes, "db", db)
    monkeypatch.setattr(routes, "s3_client", s3)
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    with TestClient(app) as client:
        result = client.get("/api/download", params={"s3_key": "file.jpg"})
        assert result.status_code == 200
        assert result.headers["x-watermark-pixel-distortion"] == "Modified-Not-Zero"
        stripped = strip_metadata(result.content)
        report = client.post("/api/forensic/verify", files={"file": ("renamed.bin", stripped)}).json()
        assert report["signal_watermark"]["authenticated"]
        assert report["decoded_payload"]["did"] == result.headers["x-watermark-download-id"]
        assert report["forensic_audit_trail"]["s3_key"] == "file.jpg"
        assert report["metadata_signature_valid"] is False
        other = create_tracking_payload("other", "other@example.com", "other.jpg")
        conflicting = inject_jpeg_watermark_bytes(stripped, generate_watermark_token(other))
        report = client.post("/api/forensic/verify", files={"file": ("conflict.jpg", conflicting)}).json()
        assert report["identity_conflict"] is True
        assert report["decoded_payload"]["did"] == result.headers["x-watermark-download-id"]
        bundle = client.post("/api/download/zip", json={"s3_keys": ["file.jpg"]})
        assert bundle.status_code == 200
        with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
            packaged = strip_metadata(archive.read("file.jpg"))
        assert extract_bytes(packaged, SECRET) in records
        # Insufficient capacity must fail before a successful download response.
        small = jpeg_bytes((32, 32))
        s3.get_file_stream = lambda key: (iter([small]), len(small), "image/jpeg")
        result = client.get("/api/download", params={"s3_key": "small.jpg"})
        assert result.status_code == 422


def test_legacy_stream_dispatch(monkeypatch):
    import core.injectors.dispatcher as dispatcher
    monkeypatch.setattr(dispatcher, "JPEG_CODEC_WATERMARK", False)
    raw = jpeg_bytes()
    result = b"".join(dispatcher.inject_watermark_stream(iter([raw[:1], raw[1:]]), "test-token", "file.jpg"))
    assert len(result) > len(raw)
    assert extract_token_from_bytes(result)[0] == "test-token"

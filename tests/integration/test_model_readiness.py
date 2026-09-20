import json
from contextlib import contextmanager
from types import SimpleNamespace

from modules.shared.readiness import readiness


def test_ai_does_not_report_ready_for_a_downloaded_checkpoint_alone(monkeypatch, tmp_path):
    checkpoint = tmp_path / "ram.pth"
    checkpoint.write_bytes(b"test fixture")
    manifest = tmp_path / "results.json"
    monkeypatch.setenv("RAM_CHECKPOINT_PATH", str(checkpoint))
    monkeypatch.setenv("AI_MODEL_READINESS_FILE", str(manifest))
    monkeypatch.setenv("REDIS_URL", "redis://test")

    @contextmanager
    def connection():
        yield SimpleNamespace(execute=lambda *_: SimpleNamespace(scalar=lambda: 1))

    monkeypatch.setattr("modules.shared.readiness.database_engine", lambda _: SimpleNamespace(connect=connection))
    monkeypatch.setattr("redis.Redis.from_url", lambda *a, **kw: SimpleNamespace(ping=lambda: True))
    for content in (None, "{", json.dumps({"ram": {"ready": True}})):
        if content is not None:
            manifest.write_text(content)
        response = readiness("enrichment", models=True)
        assert response.status_code == 503
        checks = json.loads(response.body)["checks"]
        assert checks["ram_checkpoint"] is True
        assert checks["model_initialization"] is False

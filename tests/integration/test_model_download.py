import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from model_download import download


class Response:
    def __init__(self, payload, status=206, headers=None):
        self.payload = payload
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, _size):
        result, self.payload = self.payload, b""
        return result


def test_resumes_partial_and_publishes_only_verified_checkpoint(monkeypatch, tmp_path):
    target = tmp_path / "weights.pt"
    target.write_bytes(b"abc")  # Adopt a partial library-created checkpoint.
    expected = hashlib.sha256(b"abcdef").hexdigest()

    def retrieve(request, **_):
        assert request.get_header("Range") == "bytes=3-"
        assert not target.exists(), "Incomplete checkpoint was left visible"
        return Response(b"def", headers={"Content-Range": "bytes 3-5/6"})

    monkeypatch.setattr("urllib.request.urlopen", retrieve)
    assert download("https://example.test/weights", target, expected) == str(target)
    assert target.read_bytes() == b"abcdef"
    assert not target.with_suffix(".pt.partial").exists()


def test_server_ignoring_range_restarts_instead_of_appending(monkeypatch, tmp_path):
    target = tmp_path / "weights.pt"
    target.with_suffix(".pt.partial").write_bytes(b"abc")
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: Response(b"abcdef", status=200))
    download("https://example.test/weights", target, hashlib.sha256(b"abcdef").hexdigest())
    assert target.read_bytes() == b"abcdef"


def test_corrupt_transfer_is_not_published_and_retries_from_zero(monkeypatch, tmp_path):
    target = tmp_path / "weights.pt"
    calls = []

    def retrieve(request, **_):
        calls.append(request)
        assert not target.exists()
        return Response(b"bad" if len(calls) == 1 else b"good", status=200)

    monkeypatch.setattr("urllib.request.urlopen", retrieve)
    monkeypatch.setattr("model_download.time.sleep", lambda _: None)
    download("https://example.test/weights", target, hashlib.sha256(b"good").hexdigest())
    assert len(calls) == 2
    assert target.read_bytes() == b"good"

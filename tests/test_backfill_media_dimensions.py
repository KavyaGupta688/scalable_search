"""The backfill's control flow, with the download, probe and database steps replaced by fakes."""

import contextlib
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backfill_media_dimensions.py"


def load():
    spec = importlib.util.spec_from_file_location("backfill_media_dimensions", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def fake_source(document_id):
    yield f"/tmp/{document_id}"


def test_measured_files_are_stored_then_reindexed_in_that_order():
    calls = []
    result = load().backfill(
        [("a", "image/jpeg"), ("b", "video/mp4")],
        materialize=fake_source,
        probe=lambda path, mime: {"width": 1920, "height": 1080},
        store=lambda document_id, technical: calls.append(("store", document_id, technical)),
        reindex=lambda document_id: calls.append(("reindex", document_id)),
    )
    assert result == {"measured": 2, "unmeasurable": 0, "failed": 0, "errors": []}
    assert [c[:2] for c in calls] == [("store", "a"), ("reindex", "a"), ("store", "b"), ("reindex", "b")]


def test_unmeasurable_files_are_reported_and_left_untouched():
    calls = []
    result = load().backfill(
        [("a", "application/pdf")],
        materialize=fake_source,
        probe=lambda path, mime: {},
        store=lambda *args: calls.append(args),
        reindex=lambda *args: calls.append(args),
    )
    assert result["unmeasurable"] == 1 and result["measured"] == 0
    assert calls == []


def test_one_failure_does_not_stop_the_run():
    @contextlib.contextmanager
    def source(document_id):
        if document_id == "bad":
            raise RuntimeError("source unavailable")
        yield "/tmp/ok"

    stored = []
    result = load().backfill(
        [("bad", "image/png"), ("good", "image/png")],
        materialize=source,
        probe=lambda path, mime: {"width": 800, "height": 600},
        store=lambda document_id, technical: stored.append(document_id),
        reindex=lambda document_id: None,
    )
    assert result["failed"] == 1 and result["measured"] == 1
    assert stored == ["good"]
    assert result["errors"][0][0] == "bad" and "source unavailable" in result["errors"][0][1]

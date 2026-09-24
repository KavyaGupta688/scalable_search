"""Multi-part archive writing and publishing, without a database or network."""

import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
for path in (ROOT, ROOT / "services" / "download"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
os.environ.setdefault("WATERMARK_SECRET_KEY", "x" * 40)

integrated = pytest.importorskip("integrated")  # needs the download service's dependencies


def entries(zip_path):
    with zipfile.ZipFile(zip_path) as archive:
        files = [n for n in archive.namelist() if n not in ("manifest.json", "SHA256SUMS.txt", "metadata.csv")]
        manifest = json.loads(archive.read("manifest.json"))
    return files, manifest


def fill(writer, sizes):
    for index, size in enumerate(sizes):
        writer.add(f"f{index}.bin", b"x" * size, {"filename": f"f{index}.bin"})
    return writer.close()


def test_a_new_part_starts_when_the_current_one_is_full(tmp_path):
    parts = fill(integrated.PartWriter(tmp_path, 100), [40, 40, 40, 40, 40])
    assert [p.name for p in parts] == ["part0001.zip", "part0002.zip", "part0003.zip"]
    assert [entries(p)[0] for p in parts] == [["f0.bin", "f1.bin"], ["f2.bin", "f3.bin"], ["f4.bin"]]


def test_each_part_carries_a_manifest_of_its_own_files(tmp_path):
    parts = fill(integrated.PartWriter(tmp_path, 100), [60, 60, 60])
    for part in parts:
        files, manifest = entries(part)
        assert [m["filename"] for m in manifest] == files


def test_a_file_larger_than_a_part_gets_a_part_to_itself(tmp_path):
    parts = fill(integrated.PartWriter(tmp_path, 100), [150, 10])
    assert [entries(p)[0] for p in parts] == [["f0.bin"], ["f1.bin"]]


def test_no_files_means_no_parts(tmp_path):
    assert integrated.PartWriter(tmp_path, 100).close() == []


def test_abort_closes_the_open_part(tmp_path):
    writer = integrated.PartWriter(tmp_path, 100)
    writer.add("a.bin", b"x", {})
    writer.abort()
    assert writer._zip is None
    writer.abort()  # safe to repeat


def test_a_single_part_keeps_the_plain_archive_name(tmp_path, monkeypatch):
    monkeypatch.setattr(integrated, "ROOT", tmp_path / "root")
    integrated.ROOT.mkdir()
    (tmp_path / "p.zip").write_bytes(b"1")
    integrated.publish("job", [tmp_path / "p.zip"])
    assert [p.name for p in integrated.archive_parts("job")] == ["job.zip"]


def test_several_parts_are_numbered_and_listed_in_order(tmp_path, monkeypatch):
    monkeypatch.setattr(integrated, "ROOT", tmp_path / "root")
    integrated.ROOT.mkdir()
    sources = []
    for index in range(1, 12):
        source = tmp_path / f"s{index}.zip"
        source.write_bytes(bytes([index]))
        sources.append(source)
    integrated.publish("job", sources)
    found = integrated.archive_parts("job")
    assert [p.name for p in found] == [f"job.part{i:04d}.zip" for i in range(1, 12)]
    assert found[9].read_bytes() == bytes([10])  # part 10 sorts after part 9


def test_a_failed_publish_leaves_no_partial_archive_set(tmp_path, monkeypatch):
    monkeypatch.setattr(integrated, "ROOT", tmp_path / "root")
    integrated.ROOT.mkdir()
    first = tmp_path / "a.zip"
    first.write_bytes(b"1")
    with pytest.raises(FileNotFoundError):
        integrated.publish("job", [first, tmp_path / "missing.zip"])
    assert integrated.archive_parts("job") == []


def test_other_jobs_archives_are_not_mixed_in(tmp_path, monkeypatch):
    monkeypatch.setattr(integrated, "ROOT", tmp_path)
    (tmp_path / "job.part0001.zip").write_bytes(b"1")
    (tmp_path / "job2.part0001.zip").write_bytes(b"2")
    assert [p.name for p in integrated.archive_parts("job")] == ["job.part0001.zip"]


@pytest.mark.parametrize(
    "size,text",
    [(0, "0 B"), (512, "512 B"), (1536, "1.5 KB"), (3 * 1024**2, "3.0 MB"), (5 * 1024**3, "5.0 GB"), (3 * 1024**4, "3072.0 GB")],
)
def test_sizes_are_formatted_for_error_messages(size, text):
    assert integrated.human(size) == text


def test_the_request_file_limit_follows_the_shared_setting():
    assert integrated.MAX_FILES == integrated.download_limits.MAX_FILES
    with pytest.raises(Exception):
        integrated.BatchRequest(file_ids=[])


def test_metadata_csv_and_checksums_match_delivered_bytes_in_every_part(tmp_path):
    import csv
    import hashlib
    import io
    writer = integrated.PartWriter(tmp_path, 5, include_metadata_csv=True)
    for name in ("first.bin", "second.bin"):
        writer.add(name, b"watermarked", {"filename": name, "document_id": name,
            "metadata": {"title": "=UNSAFE()", "tags": ["dog", "red"], "width": 640}})
    parts = writer.close()
    assert len(parts) == 2
    for path in parts:
        with zipfile.ZipFile(path) as archive:
            rows = list(csv.DictReader(io.StringIO(archive.read("metadata.csv").decode())))
            assert len(rows) == 1 and rows[0]["title"] == "'=UNSAFE()"
            assert rows[0]["width"] == "640"
            lines = archive.read("SHA256SUMS.txt").decode().splitlines()
            assert len(lines) == len(archive.namelist()) - 1
            for line in lines:
                checksum, name = line.split("  ", 1)
                assert hashlib.sha256(archive.read(name)).hexdigest() == checksum


def test_metadata_csv_can_be_disabled(tmp_path):
    writer = integrated.PartWriter(tmp_path, 100, include_metadata_csv=False)
    writer.add("a.bin", b"data", {"filename": "a.bin"})
    with zipfile.ZipFile(writer.close()[0]) as archive:
        assert "metadata.csv" not in archive.namelist()
        assert "SHA256SUMS.txt" in archive.namelist()


def test_preview_accepts_large_files_without_changing_selection_order(monkeypatch):
    ids = [f"file-{i}" for i in range(30)]
    rows = {key: {"file_id": key, "file_name": key + ".bin",
                 "file_size": 256 * 1024**2 if i < 6 else 1000,
                 "licence_expiry": "2029-01-01T00:00:00+00:00", "dataset_name": "Test"}
            for i, key in enumerate(ids)}
    monkeypatch.setattr(integrated, "catalog_details", lambda chosen: {key: rows[key] for key in reversed(chosen)})
    first_ten = integrated.selection_summary(ids[:10])
    assert first_ten["count"] == 10 and first_ten["within_limits"]
    assert first_ten["oversized_files"] == []
    assert first_ten["eligible_file_ids"] == ids[:10]
    assert first_ten["total_bytes"] == 6 * 256 * 1024**2 + 4000
    assert first_ten["limits"]["max_file_bytes"] == 0


def test_part_writer_streams_disk_files_and_checksums(tmp_path):
    import hashlib
    source = tmp_path / 'source.bin'
    source.write_bytes(b'large source' * 10000)
    writer = integrated.PartWriter(tmp_path, 10)
    writer.add('asset.bin', source, {'filename':'asset.bin'})
    with zipfile.ZipFile(writer.close()[0]) as archive:
        assert archive.read('asset.bin') == source.read_bytes()
        assert hashlib.sha256(source.read_bytes()).hexdigest() in archive.read('SHA256SUMS.txt').decode()


@pytest.mark.parametrize("field", ["project_name", "usage_purpose"])
def test_download_requires_nonblank_usage_details(field):
    values = {"file_ids": ["00000000-0000-0000-0000-000000000001"],
              "project_name": "Wildlife", "usage_purpose": "Campaign"}
    values[field] = "   "
    with pytest.raises(ValueError):
        integrated.BatchRequest(**values)


def test_job_and_forensic_record_persist_request_details_together():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from database.models import Base, ForensicAuditLog
    engine = create_engine("sqlite://")
    integrated.Base.metadata.create_all(engine)
    Base.metadata.create_all(engine)
    details = {"project_name": "Wildlife", "usage_purpose": "Campaign",
               "include_metadata_csv": False, "licence_expiry": "2027-01-01T00:00:00+00:00"}
    with Session(engine) as session:
        session.add(integrated.Job(id="job", owner="user", email="test@example.test", file_ids=["document"], request_details=details))
        session.add(ForensicAuditLog(download_id="watermark", job_id="job", request_details=details,
            user_id="user", user_email="test@example.test", s3_key="document", timestamp=1,
            iso_timestamp="2026-01-01", client_ip="local", token_str="signed-token", token_signature="signature"))
        session.commit()
    with Session(engine) as session:
        record = session.get(ForensicAuditLog, "watermark")
        job = session.get(integrated.Job, record.job_id)
        assert record.request_details == job.request_details == details
        assert record.token_str == "signed-token"

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from ingestion.connectors import _parse_smb_unc_path, create_connector
from ingestion.connectors.nas_nfs import NASConnectorNFS
from ingestion.connectors.nas_smb import NASConnectorSMB
from ingestion.models.connector import Connector, SourceType
from ingestion.schemas.connector import ConnectorCreate


def test_parse_smb_unc_path_supports_a_root_subdirectory():
    assert _parse_smb_unc_path(r"\\server\share\incoming\images") == (
        "server",
        "share",
        r"incoming\images",
    )


@pytest.mark.parametrize("path", ["server\\share", r"\\server", "", r"\\server\share\..\private", r"\\server\share\file:stream"])
def test_parse_smb_unc_path_rejects_invalid_paths(path):
    with pytest.raises(ValueError):
        _parse_smb_unc_path(path)


def test_factory_passes_identity_scope_and_domain_to_smb(monkeypatch):
    sessions = []
    monkeypatch.setattr(
        "ingestion.connectors.nas_smb.smbclient.register_session",
        lambda **kwargs: sessions.append(kwargs),
    )
    connector_id = uuid4()
    model = Connector(
        id=connector_id,
        name="NAS",
        source_type=SourceType.NAS_SMB,
        mount_path=r"\\server\share\incoming",
        secret_path="connectors/test",
        enumeration_max_objects=25,
    )

    source = create_connector(
        model,
        {"username": "reader", "password": "secret", "domain": "EXAMPLE"},
    )

    assert isinstance(source, NASConnectorSMB)
    assert source.connector_id == connector_id
    assert source.share_name == "share"
    assert source.root_path == "incoming"
    assert source.max_files == 25
    assert sessions[0]["username"] == r"EXAMPLE\reader"
    other = create_connector(model, {"username":"other", "password":"other-secret"})
    assert sessions[0]['connection_cache'] is not sessions[1]['connection_cache']
    assert sessions[0]['connection_timeout'] == 10
    with pytest.raises(Exception, match='inside'):
        source._safe_path(r'..\private')


def test_schema_requires_nas_protocol_to_match_source_type():
    with pytest.raises(ValueError, match="nas.protocol must be 'SMB'"):
        ConnectorCreate.model_validate(
            {
                "name": "bad",
                "source_type": "NAS_SMB",
                "nas": {"protocol": "NFS", "mount_path": r"\\server\share"},
            }
        )


@pytest.mark.asyncio
async def test_smb_enumeration_streams_and_builds_a_valid_bounded_job(monkeypatch):
    connector_id = uuid4()
    monkeypatch.setattr(
        "ingestion.connectors.nas_smb.smbclient.register_session", lambda **_: None
    )
    walk_progress = []

    def fake_walk(_path, **kwargs):
        walk_progress.append("first")
        yield (r"\\server\share\incoming", [], ["b.jpg", "a.jpg"])
        walk_progress.append("second")
        yield (r"\\server\share\incoming\later", [], ["c.jpg"])

    monkeypatch.setattr("ingestion.connectors.nas_smb.smbclient.walk", fake_walk)
    monkeypatch.setattr(
        "ingestion.connectors.nas_smb.smbclient.stat",
        lambda _path, **kwargs: SimpleNamespace(st_size=12, st_mtime=1_700_000_000),
    )
    source = NASConnectorSMB(
        server="server",
        share_name="share",
        root_path="incoming",
        username="reader",
        password="secret",
        connector_id=connector_id,
        max_files=1,
    )

    rows = [row async for row in source.enumerate()]

    assert len(rows) == 1
    job, _ = rows[0]
    assert job.connector_id == connector_id
    assert job.relative_path == "a.jpg"
    assert job.source_ref == "share/incoming/a.jpg"
    assert walk_progress == ["first"]


@pytest.mark.asyncio
async def test_nfs_enumeration_builds_valid_jobs(tmp_path):
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    connector_id = uuid4()
    source = NASConnectorNFS(
        str(tmp_path), connector_id=connector_id, max_files=1
    )

    rows = [row async for row in source.enumerate()]

    assert len(rows) == 1
    assert rows[0][0].connector_id == connector_id
    assert rows[0][0].relative_path == "a.txt"

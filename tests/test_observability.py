"""Monitoring must distinguish unknown/stale data from measured zero."""
import json
import time
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from modules.shared import monitoring_exporter as exporter
from modules.shared import observability, vector_store


def test_missing_model_manifest_is_unknown(tmp_path, monkeypatch):
    monkeypatch.setenv('AI_MODEL_READINESS_FILE', str(tmp_path/'absent.json'))
    result = exporter.read_models()
    assert result['checked_at'] is None
    assert len(result['models']) == 15
    assert all(m['initialized'] is None for m in result['models'])


def test_model_manifest_does_not_expose_internal_paths(tmp_path, monkeypatch):
    path = tmp_path/'models.json'
    path.write_text(json.dumps({'ram': {'ready': True, 'path':'private-path', 'error':'private-error'}}))
    monkeypatch.setenv('AI_MODEL_READINESS_FILE', str(path))
    result = exporter.read_models()
    assert result['models'][0] == {'name':'ram', 'initialized': True}
    assert 'private' not in json.dumps(result)


@pytest.mark.parametrize('state', [
    {'data':None,'error':None},
    {'data':{'measured_at':time.time()-100},'error':None},
    {'data':{'measured_at':time.time()},'error':'OperationalError'},
])
def test_stale_failed_or_missing_collection_is_not_success(monkeypatch, state):
    monkeypatch.setattr(exporter, 'STATE', state)
    with pytest.raises(HTTPException) as error:
        exporter.snapshot()
    assert error.value.status_code == 503
    body = exporter.metrics().body.decode()
    assert 'platform_collection_success 0.0' in body
    assert 'platform_documents' not in body


@pytest.mark.parametrize('vector,expected', [(None,200),([1.0]+[0.0]*511,200),([0.0]*3,503),([float('nan')]*512,503)])
def test_index_uses_canonical_point_and_checks_dimensions(monkeypatch, vector, expected):
    conn = Mock()
    engine = Mock()
    engine.connect.return_value.__enter__ = Mock(return_value=conn)
    engine.connect.return_value.__exit__ = Mock(return_value=False)
    conn.execute.return_value.mappings.return_value.first.side_effect = [
        {'source_ref':'s3://source/file.txt','mime_type':'text/plain'}, {'published':True}]
    monkeypatch.setattr(observability, 'database_engine', lambda *a: engine)
    q = Mock()
    q.collection_exists.return_value = False
    q.retrieve.return_value = [] if vector is None else [SimpleNamespace(vector=vector)]
    monkeypatch.setattr(vector_store, 'provision', lambda **kw: q)
    did = uuid4()
    if expected == 503:
        with pytest.raises(HTTPException) as error:
            observability.document_index(did)
        assert error.value.status_code == 503
    else:
        result = observability.document_index(did)
        assert result['indexed'] == (vector is not None)
        if vector:
            assert result['dimensions'] == 512 and result['norm'] == 1
    assert q.retrieve.call_args.kwargs['ids'] == [observability.point_id(str(did))]


def test_index_failure_is_not_reported_as_unindexed(monkeypatch):
    conn, engine = Mock(), Mock()
    engine.connect.return_value.__enter__ = Mock(return_value=conn)
    engine.connect.return_value.__exit__ = Mock(return_value=False)
    conn.execute.return_value.mappings.return_value.first.return_value = {'source_ref':'x','mime_type':'text/plain'}
    monkeypatch.setattr(observability, 'database_engine', lambda *a: engine)
    monkeypatch.setattr(vector_store, 'provision', Mock(side_effect=RuntimeError('private-url')))
    with pytest.raises(HTTPException) as error:
        observability.document_index(uuid4())
    assert error.value.status_code == 503 and 'private' not in error.value.detail

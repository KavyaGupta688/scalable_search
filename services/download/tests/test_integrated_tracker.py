import io
import uuid
import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
import integrated
from database.models import Base, ForensicAuditLog
from modules.shared.integration import assertion
from core.crypto import create_tracking_payload, generate_watermark_token
from core.injectors.jpeg_injector import inject_jpeg_watermark_bytes


@pytest.fixture
def tracker(tmp_path, monkeypatch):
    engine = create_engine('sqlite:///' + str(tmp_path/'tracker.db'), connect_args={'check_same_thread':False})
    integrated.Base.metadata.create_all(engine); Base.metadata.create_all(engine)
    monkeypatch.setattr(integrated, 'database_engine', lambda _:engine)
    monkeypatch.setattr(integrated, 'record', lambda *a,**k:None)
    monkeypatch.setattr('core.codec_forensics.inspect_signal', lambda data:None)
    payload=create_tracking_payload('user-1','reader@example.test','document-1','192.0.2.7')
    token=generate_watermark_token(payload)
    job_id=str(uuid.uuid4())
    with Session(engine) as session:
        session.add(integrated.Job(id=job_id,owner='user-1',email='reader@example.test',display_name='Reader',client_ip='192.0.2.7',file_ids=['document-1'],status='ready'))
        session.add(ForensicAuditLog(download_id=payload['did'],user_id='user-1',user_email='reader@example.test',s3_key='document-1',timestamp=payload['ts'],iso_timestamp='2026-09-21T00:00:00Z',client_ip='192.0.2.7',token_str=token,token_signature=token.rsplit('.',1)[1],status='PACKAGED',notes=job_id))
        session.commit()
    buf=io.BytesIO(); Image.new('RGB',(30,30)).save(buf,'JPEG')
    marked=inject_jpeg_watermark_bytes(buf.getvalue(), token)
    with TestClient(integrated.app) as client:
        yield client, payload, marked


def headers(role='admin'):
    return {'Authorization':'Bearer '+assertion('tester',role,'download')}


def test_tracker_admin_only_and_stored_provenance(tracker):
    client, _, data=tracker
    assert client.post('/downloads/forensic/verify',files={'file':('file.jpg',data)}).status_code == 401
    assert client.post('/downloads/forensic/verify',headers=headers('user'),files={'file':('file.jpg',data)}).status_code == 403
    result=client.post('/downloads/forensic/verify',headers=headers(),files={'file':('renamed',data)}).json()
    assert result['audit_match']
    assert result['forensic_audit_trail']['display_name'] == 'Reader'
    assert result['forensic_audit_trail']['client_ip'] == '192.0.2.7'
    assert result['forensic_audit_trail']['delivery_started_at'] is None
    assert 'token_str' not in result['forensic_audit_trail']


def test_signal_only_resolves_and_conflict_withholds_attribution(tracker,monkeypatch):
    client,payload,data=tracker
    monkeypatch.setattr('core.codec_forensics.inspect_signal',lambda data:{'authenticated':True,'download_id':payload['did'],'method':'test-adapter'})
    assert client.post('/downloads/forensic/verify',headers=headers(),files={'file':('signal.bin',b'no metadata')}).json()['audit_match']
    monkeypatch.setattr('core.codec_forensics.inspect_signal',lambda data:{'authenticated':True,'download_id':str(uuid.uuid4())})
    result=client.post('/downloads/forensic/verify',headers=headers(),files={'file':('conflict.jpg',data)}).json()
    assert result['identity_conflict'] and not result['audit_match'] and result['forensic_audit_trail'] is None


def test_unknown_file_has_no_attribution(tracker):
    client,_,_=tracker
    result=client.post('/downloads/forensic/verify',headers=headers(),files={'file':('file.csv',b'a,b\n1,2')}).json()
    assert not result['audit_match'] and result['forensic_audit_trail'] is None

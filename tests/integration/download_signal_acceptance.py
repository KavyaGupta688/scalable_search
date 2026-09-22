"""Verify the enabled signal policy with one real, previously ingested ABO image."""
import io
import json
import os
import time
import zipfile
from pathlib import Path
import httpx
from sqlalchemy import text
from modules.shared.integration import database_engine

with database_engine('search').connect() as c:
    did=c.scalar(text("SELECT file_id FROM search.file_metadata WHERE dataset_id='6aac39f7-2078-41e6-89ae-0c2b4b564c51' AND published=true AND lower(file_name) LIKE '%.jpg' ORDER BY file_size DESC LIMIT 1"))
assert did
with httpx.Client(base_url='http://gateway:8000',timeout=120) as c:
    def call(method,path,**kwargs):
        r=c.request(method,path,**kwargs);r.raise_for_status();return r
    token=call('POST','/auth/login',json={'email':os.environ['BOOTSTRAP_ADMIN_EMAIL'],'password':os.environ['BOOTSTRAP_ADMIN_PASSWORD'],'role':'admin'}).json()['access_token']
    c.headers['Authorization']='Bearer '+token
    try:
        jid=call('POST','/downloads/batch',json={'file_ids':[did]}).json()['download_id']
        for _ in range(90):
            state=call('GET','/downloads/'+jid).json()
            if state['status']!='building':break
            time.sleep(2)
        assert state['status']=='ready',state
        archive=zipfile.ZipFile(io.BytesIO(call('GET','/downloads/'+jid+'/content').content))
        assert archive.testzip() is None
        name=next(n for n in archive.namelist() if n.endswith('.jpg'))
        data=archive.read(name)
        result=call('POST','/downloads/forensic/verify',files={'file':(name,data)}).json()
        assert result['signature_valid'] and result['signal_watermark']['authenticated'] and result['audit_match'],result
        assert result['forensic_audit_trail']['watermark_methods']==['JPEG-DCT-v1','metadata-HMAC-SHA256']
        Path('/tmp/download-tracker-proof.jpg').write_bytes(data)
        print(json.dumps({'job_id':jid,'document_id':did,'execution_mode':state['execution_mode'],'verified':'real S3 bytes, JPEG signal + metadata, matching stored provenance, valid ZIP'}))
    finally: c.post('/auth/logout')

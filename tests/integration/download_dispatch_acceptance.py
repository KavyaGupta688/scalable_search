"""Real RDS/source/Redis/Celery acceptance. Creates bounded download jobs only."""
import io
import json
import os
import time
import zipfile
import httpx
from redis import Redis
from sqlalchemy import text
from modules.shared.integration import database_engine


def main():
    with database_engine('search').connect() as conn:
        ids=list(conn.execute(text("SELECT file_id FROM search.file_metadata WHERE published=true AND lower(file_name) LIKE '%.jpg' AND file_size<1500000 ORDER BY file_size LIMIT 3")).scalars())
    assert len(ids)==3, 'Need three published small JPEGs'
    client=httpx.Client(base_url='http://gateway:8000', timeout=120)
    def call(method,path,**kw):
        result=client.request(method,path,**kw); result.raise_for_status(); return result
    login=call('POST','/auth/login',json={'email':os.environ['BOOTSTRAP_ADMIN_EMAIL'],'password':os.environ['BOOTSTRAP_ADMIN_PASSWORD'],'role':'admin'}).json()
    client.headers['Authorization']='Bearer '+login['access_token']
    try:
        reports=[]
        for expected,files,busy in [('direct',ids[:1],False),('celery',ids,False),('celery',ids[:1],True)]:
            redis=Redis.from_url(os.environ['REDIS_URL'])
            lock=redis.lock('download:direct-slot',timeout=150,blocking=False)
            if busy: assert lock.acquire(blocking=False)
            try:
                job=call('POST','/downloads/batch',json={'file_ids':files},headers={'X-Forwarded-For':'203.0.113.99','X-User-Name':'Forged name','X-User-Id':'forged-user'}).json()['download_id']
                for _ in range(90):
                    state=call('GET','/downloads/'+job).json()
                    if state['status']!='building': break
                    time.sleep(2)
                assert state['status']=='ready',state
                assert state['execution_mode']==expected,state
                archive=zipfile.ZipFile(io.BytesIO(call('GET','/downloads/'+job+'/content').content))
                assert archive.testzip() is None
                name=next(n for n in archive.namelist() if n.endswith('.jpg'))
                traced=call('POST','/downloads/forensic/verify',files={'file':(name,archive.read(name))}).json()
                assert traced['audit_match'],traced
                trail=traced['forensic_audit_trail']
                assert trail['user_email']==os.environ['BOOTSTRAP_ADMIN_EMAIL']
                assert trail['client_ip'] not in ('internal','203.0.113.99',None)
                assert trail['display_name']!='Forged name'
                assert trail['delivery_started_at']
                reports.append({'job_id':job,'files':len(files),'mode':state['execution_mode'],'busy_fallback':busy,'forensic_match':True,'gateway_ip_recorded':True})
            finally:
                if busy and lock.owned(): lock.release()
        print(json.dumps(reports,indent=2))
    finally:
        client.post('/auth/logout'); client.close()


if __name__=='__main__': main()

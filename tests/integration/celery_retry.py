"""Exercise administrative retry through the actual Celery worker (missing-model fixture)."""
import os,time,httpx
from sqlalchemy import text
from modules.shared.integration import database_engine
c=httpx.Client(base_url='http://gateway:8000',timeout=30)
t=c.post('/auth/login',json={'email':os.environ['BOOTSTRAP_ADMIN_EMAIL'],'password':os.environ['BOOTSTRAP_ADMIN_PASSWORD'],'role':'admin'}).json()['access_token']
with database_engine('enrichment').connect() as db:
 did=str(db.execute(text("SELECT document_id FROM enrichment_tasks WHERE status='failed_terminal' ORDER BY document_id DESC LIMIT 1")).scalar_one())
r=c.post('/ai/retry/'+did,headers={'Authorization':'Bearer '+t});assert r.status_code==200,(r.status_code,r.text[:200])
for _ in range(90):
 with database_engine('enrichment').connect() as db:
  task=db.execute(text('SELECT status,retry_count FROM enrichment_tasks WHERE document_id=:id'),{'id':did}).one()
 if task.status=='failed_terminal' and task.retry_count>=3:break
 time.sleep(1)
assert task.status=='failed_terminal' and task.retry_count>=3,task
print('PASS: authenticated manual AI retry dispatched through Celery and persisted bounded missing-model failure')

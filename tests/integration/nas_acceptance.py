"""Bounded NAS connection test; scan only after a successful real connection.

Credentials are supplied in an ignored JSON file, never printed or committed.
Set NAS_ACCEPTANCE_CREDENTIALS to that container-visible file.
"""
import json
import os
from pathlib import Path
import httpx


def main():
    credentials = json.loads(Path(os.environ['NAS_ACCEPTANCE_CREDENTIALS']).read_text(encoding='utf-8-sig'))
    name=os.getenv('NAS_ACCEPTANCE_NAME','NAS Tagged Search Test')
    path=os.getenv('NAS_ACCEPTANCE_PATH',r'\\100.72.198.49\IngestionDemo\tagged-search-test-01')
    maximum=int(os.getenv('NAS_ACCEPTANCE_MAX_FILES','20'))
    with httpx.Client(base_url='http://gateway:8000',timeout=90) as client:
        response=client.post('/auth/login',json={'email':os.environ['BOOTSTRAP_ADMIN_EMAIL'],'password':os.environ['BOOTSTRAP_ADMIN_PASSWORD'],'role':'admin'})
        response.raise_for_status()
        client.headers['Authorization']='Bearer '+response.json()['access_token']
        try:
            response=client.get('/admin/connectors'); response.raise_for_status()
            rows=response.json()
            if isinstance(rows,dict): rows=rows.get('connectors',rows.get('items',[]))
            matches=[c for c in rows if c['name']==name and not c.get('archived_at')]
            if matches:
                connector=matches[0]
                assert connector['mount_path']==path and connector['enumeration_max_objects']==maximum, 'Existing connector scope differs; refusing to scan'
            else:
                response=client.post('/admin/connectors',json={'name':name,'source_type':'NAS_SMB','nas':{'protocol':'SMB','mount_path':path,'max_files':maximum,**credentials}})
                response.raise_for_status(); connector=response.json()
            cid=connector['id']
            response=client.post(f'/admin/connectors/{cid}/test'); response.raise_for_status()
            test=response.json()
            report={'connector_id':cid,'name':name,'maximum_files':maximum,'test':test,'run_id':None}
            if test['status'].lower()=='verified':
                response=client.post(f'/admin/ingestion/trigger/{cid}'); response.raise_for_status()
                report['run_id']=response.json()['run_id']
            print(json.dumps(report,indent=2))
        finally:
            client.post('/auth/logout')


if __name__=='__main__': main()

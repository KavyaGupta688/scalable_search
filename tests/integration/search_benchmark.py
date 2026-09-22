"""Measure real gateway latency without replacing model or search responses."""
import json
import os
import statistics
import time
import httpx


def main():
    report=[]
    with httpx.Client(base_url=os.getenv('TEST_GATEWAY_URL','http://gateway:8000'),timeout=180) as c:
        login=c.post('/auth/login',json={'email':os.environ['BOOTSTRAP_ADMIN_EMAIL'],
            'password':os.environ['BOOTSTRAP_ADMIN_PASSWORD'],'role':'admin'})
        login.raise_for_status()
        c.headers['Authorization']='Bearer '+login.json()['access_token']
        try:
            for mode in ('text','hybrid','vector'):
                for query in ('chair','book','chair'):
                    start=time.perf_counter()
                    r=c.post('/search',json={'query':query,'search_mode':mode,'limit':10})
                    elapsed=(time.perf_counter()-start)*1000
                    r.raise_for_status()
                    d=r.json()
                    report.append({'mode':mode,'query':query,'wall_ms':round(elapsed,1),
                        'reported_ms':d['execution_time_ms'],'total':d['total']})
        finally:
            c.post('/auth/logout').raise_for_status()
    print(json.dumps({'requests':report,'median_ms':{m:round(statistics.median(x['wall_ms'] for x in report if x['mode']==m),1) for m in ('text','hybrid','vector')}},indent=2))


if __name__=='__main__':
    main()

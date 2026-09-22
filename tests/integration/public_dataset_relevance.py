"""Report real ABO retrieval ranks without replacing or grading model outputs as ground truth.

Expected filenames come from manual inspection of the six public source images.
Run in gateway after enrichment. Uses public captions/tags, never modifies them.
"""
import json
import os
import time
import httpx
import argparse
from uuid import UUID


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('photo_connector', type=UUID)
    parser.add_argument('paper_connector', type=UUID)
    args = parser.parse_args()
    photo_dataset, paper_dataset = str(args.photo_connector), str(args.paper_connector)
    cases = [('suitcase with wheels', '00000529.jpg'), ('photo frame', '00003a93.jpg'),
             ('laundry basket', '000088e1.jpg'), ('striped rug', '0000b301.jpg'),
             ('metal wrenches', '0000b9b8.jpg'), ('phone case', '0000bd76.jpg')]
    report = {'note':'Small manually inspected sample, not a labelled accuracy benchmark', 'queries':[]}
    with httpx.Client(base_url='http://gateway:8000', timeout=120) as c:
        r = c.post('/auth/login', json={'email':os.environ['BOOTSTRAP_ADMIN_EMAIL'],
                   'password':os.environ['BOOTSTRAP_ADMIN_PASSWORD'], 'role':'admin'})
        r.raise_for_status()
        c.headers['Authorization'] = 'Bearer '+r.json()['access_token']
        try:
            for mode in ('text','hybrid','vector'):
                for query, filename in cases + [('Amazon Berkeley Objects dataset','ABO_CVPR2022.pdf')]:
                    cid = paper_dataset if filename.endswith('.pdf') else photo_dataset
                    start = time.perf_counter()
                    r = c.post('/search', json={'query':query,'search_mode':mode,'limit':10,'filters':{'dataset_ids':[cid]}})
                    r.raise_for_status(); data=r.json()
                    filenames=[x['file_name'] for x in data['results']]
                    report['queries'].append({'mode':mode,'query':query,'expected_file':filename,
                        'rank':filenames.index(filename)+1 if filename in filenames else None,
                        'wall_ms':round((time.perf_counter()-start)*1000), 'returned_files':filenames})
            report['catalog'] = []
            for cid in (photo_dataset,paper_dataset):
                r = c.post('/search',json={'query':'*','search_mode':'text','limit':100,'filters':{'dataset_ids':[cid]}})
                r.raise_for_status()
                for row in r.json()['results']:
                    report['catalog'].append({k:row.get(k) for k in ('file_id','file_name','title','description','caption','tags','file_type','dataset_name')})
        finally:
            c.post('/auth/logout').raise_for_status()
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()

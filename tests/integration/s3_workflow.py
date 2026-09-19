"""Bounded S3 emulator ingestion and unchanged-rescan acceptance. Synthetic keys only."""

import io, os, time, uuid
import boto3, httpx
from PIL import Image
from sqlalchemy import text
from modules.shared.integration import database_engine

c = httpx.Client(base_url="http://gateway:8000", timeout=90)


def call(method, path, status=200, **kw):
    r = c.request(method, path, **kw)
    assert r.status_code == status, (path, r.status_code, r.text[:500])
    return r


h = {
    "Authorization": "Bearer "
    + call(
        "POST",
        "/auth/login",
        json={
            "email": os.environ["BOOTSTRAP_ADMIN_EMAIL"],
            "password": os.environ["BOOTSTRAP_ADMIN_PASSWORD"],
            "role": "admin",
        },
    ).json()["access_token"]
}
s3 = boto3.client(
    "s3",
    endpoint_url="http://s3-test:5000",
    aws_access_key_id="synthetic-acceptance",
    aws_secret_access_key="synthetic-acceptance",
    region_name="us-east-1",
)
bucket = "acceptance-" + uuid.uuid4().hex[:12]
s3.create_bucket(Bucket=bucket)
buffer = io.BytesIO()
Image.new("RGB", (96, 96), (73, 142, int(bucket[-2:], 16))).save(buffer, "PNG")
payload = buffer.getvalue()
s3.put_object(Bucket=bucket, Key="image.png", Body=payload)
s3.put_object(
    Bucket=bucket,
    Key="metadata.csv",
    Body=b"id,filename,title,category,tags\n1,image.png,S3 acceptance image,Acceptance,synthetic\n",
)
cid = call(
    "POST",
    "/admin/connectors",
    201,
    headers=h,
    json={
        "name": bucket,
        "source_type": "S3",
        "s3": {
            "endpoint_url": "http://s3-test:5000",
            "bucket": bucket,
            "access_key": "synthetic-acceptance",
            "secret_key": "synthetic-acceptance",
            "max_objects": 3,
        },
    },
).json()["id"]
call("POST", f"/admin/connectors/{cid}/test", headers=h)


def scan():
    rid = call("POST", f"/admin/ingestion/trigger/{cid}", headers=h).json()["run_id"]
    for _ in range(90):
        result = call("GET", f"/admin/ingestion/runs/{rid}", headers=h).json()
        if result["status"] in ("completed", "completed_with_errors", "failed"):
            break
        time.sleep(1)
    assert result["status"] == "completed", result
    return call("GET", f"/admin/ingestion/runs/{rid}/items", headers=h).json()


items = scan()
ids = [i["document_id"] for i in items if i.get("document_id")]
assert len(ids) == 1, items
did = ids[0]
assert call("GET", f"/documents/{did}/content", headers=h).content == payload
with database_engine("ingestion").connect() as db:
    before = db.execute(
        text(
            "SELECT count(*) FROM integration_outbox WHERE kind='ai-processing' AND payload->>'document_id'=:id"
        ),
        {"id": did},
    ).scalar()
again = scan()
with database_engine("ingestion").connect() as db:
    after = db.execute(
        text(
            "SELECT count(*) FROM integration_outbox WHERE kind='ai-processing' AND payload->>'document_id'=:id"
        ),
        {"id": did},
    ).scalar()
assert before == after == 1, (before, after, again)
print(
    "PASS: S3 source access, real ingestion, canonical ID, unchanged rescan, one AI delivery record. document_id="
    + did
)

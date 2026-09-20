"""Exercise the AI publication contract in a disposable migrated database.

Requires an explicit legacy_acceptance_* database and integration_validation_*
Qdrant collection. Synthetic metadata/vectors remain confined to those resources.
Run in the Search container; application source files and models are not changed.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from sqlalchemy import text
from sqlalchemy.engine import make_url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database")
    parser.add_argument("collection")
    args = parser.parse_args()
    import re
    assert re.fullmatch(r"legacy_acceptance_[a-f0-9]{8}", args.database)
    assert re.fullmatch(r"integration_validation_[a-f0-9]{10}", args.collection)
    for key in ("DATABASE_URL", "DATABASE_URL_SYNC"):
        os.environ[key] = make_url(os.environ[key]).set(database=args.database).render_as_string(hide_password=False)
    os.environ["DATABASE_SCHEMA"] = "search"
    os.environ["QDRANT_COLLECTION_NAME"] = args.collection
    # Search currently uses PostgreSQL for discovery history; a separate Redis
    # DB prevents test cache keys from sharing the live runtime's namespace.
    os.environ["REDIS_DB"] = "15"
    from modules.shared.integration import database_engine, assertion, point_id
    from modules.shared.vector_store import client, collection
    from modules.shared.indexer import index_document
    from modules.shared.catalog import require_downloadable
    from qdrant_client import models
    from fastapi import HTTPException

    engine = database_engine("search")
    cid, eid = str(uuid.uuid4()), str(uuid.uuid4())
    base = {"contains_pii": True, "nsfw_flagged": False, "analysis_incomplete": False, "toxicity_score": 0.01}
    cases = [
        ("completed", base, True),
        ("partial", base, True),
        ("completed", {**base, "nsfw_flagged": True}, False),
        ("completed", {**base, "toxicity_score": 0.9}, False),
        ("completed", {**base, "analysis_incomplete": True}, False),
        ("needs_review", base, False),
        ("queued", base, False),
        ("failed_terminal", base, False),
    ]
    ids = [str(uuid.uuid4()) for _ in cases]
    with engine.begin() as c:
        assert c.execute(text("SELECT current_database()")).scalar_one() == args.database
        c.execute(text("INSERT INTO ingestion.connectors(id,name,source_type,secret_path,status) VALUES (:id,'Acceptance PII policy','S3','test-only-no-credentials','verified')"), {"id": cid})
        c.execute(text("INSERT INTO ingestion.license_entitlements(id,license_subject_id,license_start_at,expires_at) VALUES (:id,:subject,now(),now()+interval '1 day')"), {"id": eid, "subject": "test-only-" + eid})
        for did, (status, safety, _) in zip(ids, cases):
            c.execute(text("INSERT INTO ingestion.documents(id,checksum_sha256,size_bytes,mime_type,source_connector_id,source_ref,entitlement_id) VALUES (:id,:checksum,1,'image/jpeg',:cid,'test-only/acceptance.jpg',:eid)"),
                      {"id": did, "checksum": hashlib.sha256(did.encode()).hexdigest(), "cid": cid, "eid": eid})
            c.execute(text("INSERT INTO enrichment.enrichment_tasks(document_id,status) VALUES (:id,:status)"), {"id": did, "status": status})
            c.execute(text("""INSERT INTO enrichment.document_enrichment_metadata
                (id,document_id,model_version,enrichment_version,metadata_version,generated_tags,
                 short_description,privacy_safety_labels,restricted_metadata,enrichment_status)
                VALUES (:mid,:id,'test-only','policy-test','1.0','["acceptance"]'::jsonb,
                'Acceptance annotation policy',CAST(:safety AS jsonb),'{"pii_details":"test-restricted"}'::jsonb,:status)"""),
                {"mid": str(uuid.uuid4()), "id": did, "status": status, "safety": json.dumps(safety)})
    q = client()
    q.upsert(collection(), points=[models.PointStruct(id=point_id(did), vector=[1.0]+[0.0]*511,
              payload={"document_id": did, "file_id": did, "published": True}) for did in ids], wait=True)
    for did in ids:
        index_document(did)
        index_document(did)
    with engine.connect() as c:
        rows = list(c.execute(text("SELECT file_id,published,pii_detected FROM file_metadata WHERE dataset_id=:cid"), {"cid": cid}))
        assert len(rows) == len(ids)
        assert {r.file_id for r in rows if r.published} == set(ids[:2])
        assert all(r.pii_detected for r in rows)
    require_downloadable(ids[:2])
    for did in ids[2:]:
        try:
            require_downloadable([did])
            raise AssertionError("Restricted file was downloadable")
        except HTTPException as e:
            assert e.status_code == 403

    sys.path.insert(0, str(Path("/app/services/search/backend")))
    from app.main import app
    from httpx import AsyncClient, ASGITransport

    async def check_apis():
        headers = {"Authorization": "Bearer " + assertion("pii-policy-test", "user", "search")}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers, timeout=120) as http:
            async def search(expected):
                r = await http.post("/search", json={"query": "acceptance", "search_mode": "text", "filters": {"dataset_ids": [cid], "pii_detected": True}})
                assert r.status_code == 200, r.text
                data = r.json()
                assert {x["file_id"] for x in data["results"]} == set(expected), data
                assert data["total"] == data["facets"]["total_matches"] == len(expected)
            await search(ids[:2])
            for did in ids[:2]:
                r = await http.get("/files/" + did)
                assert r.status_code == 200
                assert "test-restricted" not in r.text and "restricted_metadata" not in r.text
            for did in ids[2:]:
                assert (await http.get("/files/" + did)).status_code == 404
                assert (await http.post("/search/similar", json={"file_id": did})).status_code == 404
            # Leave cached vectors/publication stale deliberately: current task
            # and entitlement state must still deny read/download access.
            with engine.begin() as c:
                c.execute(text("UPDATE enrichment.enrichment_tasks SET status='needs_review' WHERE document_id=:id"), {"id": ids[0]})
            await search([ids[1]])
            assert (await http.get("/files/" + ids[0])).status_code == 404
            with engine.begin() as c:
                c.execute(text("UPDATE ingestion.license_entitlements SET status='expired' WHERE id=:id"), {"id": eid})
            await search([])
            assert (await http.get("/files/" + ids[1])).status_code == 404
            try:
                require_downloadable(ids[:2])
                raise AssertionError("Expired/review data remained downloadable")
            except HTTPException as e:
                assert e.status_code == 403
        # Restore only this disposable fixture for the existing Search suite.
        with engine.begin() as c:
            c.execute(text("UPDATE ingestion.license_entitlements SET status='active' WHERE id=:id"), {"id": eid})
            c.execute(text("UPDATE enrichment.enrichment_tasks SET status='completed' WHERE document_id=:id"), {"id": ids[0]})
    asyncio.run(check_apis())
    print("PASS: PII annotations, unsafe/review exclusions, idempotent projection, restricted details, stale-vector denial and current entitlements", flush=True)
    subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "app/tests", "-q"], cwd="/app/services/search/backend", check=True)


if __name__ == "__main__":
    main()

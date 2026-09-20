"""Verify actual AI outputs via normal APIs; never insert catalog/model fixtures.

Creates one standard test account and one download job in the approved RDS
integration database. Source documents, entitlements and AI statuses are read-only.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import secrets
import time
import uuid
import zipfile

import httpx
from sqlalchemy import text
from modules.shared.integration import database_engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("connector_id")
    args = parser.parse_args()
    settings = dict(line.split("=", 1) for line in Path(".integration/stack.env").read_text().splitlines()
                    if "=" in line and not line.startswith("#"))
    with database_engine("ingestion").connect() as conn:
        assert conn.execute(text("SELECT current_database()")).scalar_one() == "smsprsm_integration"
        docs = list(conn.execute(text("SELECT id,checksum_sha256,size_bytes FROM documents WHERE source_connector_id=:id"),
                                 {"id": args.connector_id}).mappings())
    assert 0 < len(docs) <= 5
    ids = [str(d["id"]) for d in docs]
    report = {"document_ids": ids, "checks": []}
    with database_engine("enrichment").connect() as conn:
        rows = list(conn.execute(text("SELECT document_id,status,current_stage,error_message FROM enrichment_tasks WHERE document_id=ANY(CAST(:ids AS uuid[]))"),
                                 {"ids": ids}).mappings())
    report["tasks"] = [{**r, "document_id": str(r["document_id"])} for r in rows]
    assert len(rows) == len(ids) and all(r["status"] in ("completed", "partial", "needs_review") for r in rows), report["tasks"]
    with database_engine("search").connect() as conn:
        published = {r[0] for r in conn.execute(text("SELECT file_id FROM file_metadata WHERE dataset_id=:id AND published"), {"id": args.connector_id})}
    assert published, "No safety-cleared actual output available to test"
    with httpx.Client(base_url="http://gateway:8000", timeout=120) as client:
        def call(method, path, expected=200, **kwargs):
            response = client.request(method, path, **kwargs)
            assert response.status_code == expected, (path, response.status_code, response.text[:300])
            return response

        admin = call("POST", "/auth/login", json={"email": settings["BOOTSTRAP_ADMIN_EMAIL"],
                     "password": settings["BOOTSTRAP_ADMIN_PASSWORD"], "role": "admin"}).json()
        admin_headers = {"Authorization": "Bearer " + admin["access_token"]}
        email, password = "actual-ai-" + uuid.uuid4().hex[:10] + "@example.test", secrets.token_urlsafe(24)
        registered = call("POST", "/auth/register", json={"email": email, "password": password, "role": "user"}).json()
        user = call("POST", "/auth/login", json={"email": email, "password": password, "role": "user"}).json()
        user_headers = {"Authorization": "Bearer " + user["access_token"]}
        report["test_account"] = email
        for role, headers in [("admin", admin_headers), ("user", user_headers)]:
            for mode in ("text", "hybrid", "vector"):
                result = call("POST", "/search", headers=headers, json={"query": "sample", "search_mode": mode,
                              "filters": {"dataset_ids": [args.connector_id]}, "limit": 50}).json()
                found = {r["file_id"] for r in result["results"]}
                assert found == published, (role, mode, found, published)
                report["checks"].append(role + " " + mode + " search")
        for doc in docs:
            did = str(doc["id"])
            if did not in published:
                call("GET", "/files/" + did, headers=user_headers, expected=404)
                call("POST", "/downloads/batch", headers=user_headers, expected=403, json={"file_ids": [did]})
                continue
            call("GET", "/files/" + did, headers=user_headers)
            content = call("GET", "/documents/" + did + "/content", headers=user_headers).content
            assert len(content) == doc["size_bytes"] and hashlib.sha256(content).hexdigest() == doc["checksum_sha256"]
            similar = call("POST", "/search/similar", headers=user_headers, json={"file_id": did}).json()
            assert did not in {r["file_id"] for r in similar["results"]}
        report["checks"].append("details, protected source checksums, similarity and visibility")
        job = call("POST", "/downloads/batch", expected=202, headers=user_headers,
                   json={"file_ids": sorted(published)}).json()["download_id"]
        for _ in range(60):
            state = call("GET", "/downloads/" + job, headers=user_headers).json()
            if state["status"] != "building":
                break
            time.sleep(2)
        assert state["status"] == "ready", state
        archive = zipfile.ZipFile(io.BytesIO(call("GET", "/downloads/" + job + "/content", headers=user_headers).content))
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(published) + 1
        audio = next(n for n in archive.namelist() if n.endswith((".mp3", ".wav")))
        verified = call("POST", "/downloads/forensic/verify", headers=admin_headers,
                        files={"file": (audio, archive.read(audio))}).json()
        assert verified["signature_valid"] and verified["audit_match"]
        report.update(download_id=job, packaged_files=len(published), ready=True)
        report["checks"].append("persistent packaging, archive retrieval and metadata forensic verification")
        call("POST", "/auth/logout", expected=204, headers=user_headers)
        call("POST", "/auth/logout", expected=204, headers=admin_headers)
    with database_engine("audit").connect() as conn:
        actions = {r[0] for r in conn.execute(text("SELECT action FROM audit_events WHERE entity_id=:job OR actor=:actor"),
                                             {"job": job, "actor": registered["id"]})}
    assert {"SEARCH", "DOWNLOAD_DELIVERY_STARTED"}.issubset(actions), actions
    report["checks"].append("persistent Audit")
    Path("/models/provisioning/actual-workflow.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()

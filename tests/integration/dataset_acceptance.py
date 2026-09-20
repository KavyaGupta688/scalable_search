"""Real-source acceptance for one explicitly selected connector and ingestion run.

Run in the AI container. Never writes source content or substitutes model outputs.
Creates test accounts, a bounded unchanged rescan, download jobs and Audit events.
Keeps a resumable local report in the model volume. Browser coverage is separate.
"""
import argparse
import collections
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


def snapshot(connector, run):
    with database_engine("ingestion").connect() as c:
        assert c.execute(text("SELECT current_database()")).scalar_one() == "smsprsm_integration"
        result = dict(c.execute(text("SELECT status,enumerated_count,metadata_files_skipped,terminal_count,succeeded_count,duplicate_count,skipped_count,failed_count,rejected_count,bytes_processed FROM ingestion_runs WHERE id=:id AND connector_id=:cid"), {"id": run, "cid": connector}).mappings().one())
        docs = [dict(r) for r in c.execute(text("SELECT DISTINCT d.id,d.size_bytes,d.checksum_sha256,d.mime_type,d.source_ref,d.source_connector_id FROM documents d JOIN source_assets a ON a.document_id=d.id WHERE a.source_connector_id=:id"), {"id": connector}).mappings()]
        tasks = [dict(r) for r in c.execute(text("SELECT t.document_id,t.status,t.current_stage,t.error_message,t.retry_count FROM enrichment.enrichment_tasks t WHERE document_id IN (SELECT document_id FROM source_assets WHERE source_connector_id=:id)"), {"id": connector}).mappings()]
    return result, docs, tasks


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("connector_id", type=uuid.UUID)
    p.add_argument("run_id", type=uuid.UUID)
    p.add_argument("--wait-seconds", type=int, default=10800)
    args = p.parse_args()
    cid, rid = str(args.connector_id), str(args.run_id)
    output = Path("/models/provisioning/dataset-" + cid + "-results.json")
    report = {"connector_id": cid, "run_id": rid, "checks": [], "limitations": [], "started_at": time.time()}

    def save():
        output.write_text(json.dumps(report, indent=2, default=str))

    def passed(name):
        report["checks"].append(name)
        save()
        print("PASS:", name, flush=True)

    deadline, previous = time.monotonic() + args.wait_seconds, None
    while True:
        run, docs, tasks = snapshot(cid, rid)
        counts = dict(collections.Counter(t["status"] for t in tasks))
        state = {"ingestion": run, "documents": len(docs), "ai": counts}
        report.update(progress=state, tasks=tasks)
        save()
        if state != previous:
            print(json.dumps(state), flush=True)
            previous = state
        if run["status"] in ("completed", "completed_with_errors", "failed") and len(tasks) == len(docs) and all(t["status"] in ("completed", "partial", "needs_review", "failed_terminal") for t in tasks):
            break
        if time.monotonic() >= deadline:
            raise TimeoutError("Dataset processing is not finished; progress report retained")
        time.sleep(30)
    assert run["status"] == "completed" and not run["failed_count"] and not run["rejected_count"], run
    assert run["terminal_count"] == run["enumerated_count"]
    passed("all enumerated content processed; manifests skipped and duplicates recorded")
    failures = [t for t in tasks if t["status"] == "failed_terminal"]
    if failures:
        report["limitations"].append({"terminal_ai_failures": failures})
    with database_engine("search").connect() as c:
        # Allow the durable indexer to catch up after the final AI commit.
        for _ in range(60):
            indexed = [dict(r) for r in c.execute(text("SELECT file_id,file_type,published FROM file_metadata WHERE file_id IN (SELECT document_id::text FROM ingestion.source_assets WHERE source_connector_id=:id)"), {"id": cid}).mappings()]
            if len(indexed) == len(docs):
                break
            time.sleep(2)
    published = {r["file_id"] for r in indexed if r["published"]}
    report["published_count"] = len(published)
    report["document_count"] = len(docs)
    assert published, "No cleared model outputs available"
    settings = dict(l.split("=", 1) for l in Path(".integration/stack.env").read_text().splitlines() if "=" in l and not l.startswith("#"))
    with httpx.Client(base_url="http://gateway:8000", timeout=180) as client:
        def call(method, path, expected=200, **kwargs):
            r = client.request(method, path, **kwargs)
            read_only = method == "GET" or (method == "POST" and path in ("/search", "/search/similar"))
            if expected == 200 and read_only and r.status_code in (502, 503, 504):
                # Preserve the reliability finding; never retry a mutation or
                # turn a transient failure into an unqualified acceptance pass.
                report["limitations"].append({"transient_read_failure": path, "status": r.status_code})
                save()
                print("RETRY read-only request:", path, r.status_code, flush=True)
                time.sleep(2)
                r = client.request(method, path, **kwargs)
            assert r.status_code == expected, (path, r.status_code, r.text[:250])
            return r

        def login(email, password, role):
            result = call("POST", "/auth/login", json={"email": email, "password": password, "role": role}).json()
            return {"Authorization": "Bearer " + result["access_token"]}

        admin = login(settings["BOOTSTRAP_ADMIN_EMAIL"], settings["BOOTSTRAP_ADMIN_PASSWORD"], "admin")
        email, password = "dataset-" + uuid.uuid4().hex[:12] + "@example.test", secrets.token_urlsafe(24)
        account = call("POST", "/auth/register", json={"email": email, "password": password, "role": "user"}).json()
        user = login(email, password, "user")
        report["test_account"] = email
        for path in ("/admin/connectors", "/ai/tasks", "/auth/users"):
            call("GET", path, headers=user, expected=403)
        call("POST", "/auth/login", json={"email": email, "password": "deliberately-incorrect", "role": "user"}, expected=401)
        passed("real role permissions and incorrect-password rejection")
        for role, h in (("admin", admin), ("user", user)):
            for mode in ("text", "hybrid", "vector"):
                result = call("POST", "/search", headers=h, json={"query": "test asset", "search_mode": mode, "filters": {"dataset_ids": [cid]}, "limit": 100}).json()
                assert {r["file_id"] for r in result["results"]} == published, (role, mode, result["total"], len(published))
                assert result["facets"]["total_matches"] == len(published)
            passed(role + " text, hybrid and vector discovery with dataset isolation")
        all_ids = []
        for offset in range(0, len(published), 10):
            data = call("POST", "/search", headers=user, json={"query": "test asset", "search_mode": "text", "filters": {"dataset_ids": [cid]}, "limit": 10, "offset": offset}).json()
            all_ids.extend(r["file_id"] for r in data["results"])
        assert len(all_ids) == len(set(all_ids)) and set(all_ids) == published
        for modality in {r["file_type"] for r in indexed if r["published"]}:
            data = call("POST", "/search", headers=user, json={"query": "test asset", "search_mode": "text", "filters": {"dataset_ids": [cid], "file_types": [modality]}, "limit": 100}).json()
            expected = {r["file_id"] for r in indexed if r["published"] and r["file_type"] == modality}
            assert {r["file_id"] for r in data["results"]} == expected
        passed("pagination, facets and all available modality filters")
        small, oversized = [], []
        for doc in docs:
            did = str(doc["id"])
            if did not in published:
                call("GET", "/files/" + did, headers=user, expected=404)
                call("GET", "/documents/" + did + "/content", headers=user, expected=403)
                call("POST", "/downloads/batch", headers=user, expected=403, json={"file_ids": [did]})
                continue
            result = call("GET", "/files/" + did, headers=user).json()
            assert '"restricted_metadata"' not in json.dumps(result)
            assert '"pii_details"' not in json.dumps(result)
            if doc["size_bytes"] > 128 * 1024**2:
                oversized.append(did)
                # Verify protected headers and cancellation without re-reading
                # hundreds of megabytes already verified by ingestion and AI.
                with client.stream("GET", "/documents/" + did + "/content", headers=user) as r:
                    assert r.status_code == 200
                    assert int(r.headers["Content-Length"]) == doc["size_bytes"]
                    assert r.headers["Cache-Control"] == "no-store"
            else:
                small.append(did)
                raw = call("GET", "/documents/" + did + "/content", headers=user).content
                assert len(raw) == doc["size_bytes"] and hashlib.sha256(raw).hexdigest() == doc["checksum_sha256"]
            result = call("POST", "/search/similar", headers=user, json={"file_id": did, "filters": {"dataset_ids": [cid]}}).json()
            assert did not in {r["file_id"] for r in result["results"]}
            assert {r["file_id"] for r in result["results"]} <= published
            print("VERIFIED document:", did, flush=True)
        passed("canonical details, restricted-field exclusion, source checksums, cancellation and similarity")

        def package(ids):
            job = call("POST", "/downloads/batch", expected=202, headers=user, json={"file_ids": ids}).json()["download_id"]
            for _ in range(90):
                state = call("GET", "/downloads/" + job, headers=user).json()
                if state["status"] != "building":
                    return job, state
                time.sleep(2)
            raise TimeoutError("Download did not reach a terminal state")

        if small:
            job, state = package(small)
            report["download_id"] = job
            report["download_state"] = state
            assert state["status"] == "ready", state
            other_email = "ownership-" + uuid.uuid4().hex[:12] + "@example.test"
            other_password = secrets.token_urlsafe(24)
            call("POST", "/auth/register", json={"email": other_email, "password": other_password, "role": "user"})
            other = login(other_email, other_password, "user")
            call("GET", "/downloads/" + job, headers=other, expected=404)
            call("GET", "/downloads/" + job + "/content", headers=other, expected=404)
            other_history = call("GET", "/downloads", headers=other).json()["downloads"]
            assert all(j["download_id"] != job for j in other_history)
            call("POST", "/auth/logout", headers=other, expected=204)
            passed("another standard user cannot inspect or retrieve the download")
            archive = zipfile.ZipFile(io.BytesIO(call("GET", "/downloads/" + job + "/content", headers=user).content))
            assert archive.testzip() is None and len(archive.namelist()) == len(small) + 1
            representatives = {}
            for name in archive.namelist():
                suffix = Path(name).suffix.lower()
                if suffix in (".jpg", ".png", ".wav", ".mp3", ".mp4", ".mov", ".avi"):
                    representatives.setdefault(suffix, name)
            for name in representatives.values():
                verification = call("POST", "/downloads/forensic/verify", headers=admin, files={"file": (name, archive.read(name))}).json()
                assert verification["signature_valid"] and verification["audit_match"], name
            passed("persistent small-file archive, ZIP integrity and supported-format forensic verification")
        if oversized:
            job, state = package([oversized[0]])
            report["oversize_job"] = job
            assert state["status"] == "failed" and "size limit" in state["error"].lower(), state
            assert state["download_url"] is None
            call("GET", "/downloads/" + job + "/content", headers=user, expected=409)
            report["limitations"].append({"files_above_download_limit": len(oversized), "per_file_limit_bytes": 128 * 1024**2})
            passed("oversized download fails visibly and exposes no archive")
        # Existing persisted content should be skipped rather than re-enriched.
        before = len(docs)
        rescan = call("POST", "/admin/ingestion/trigger/" + cid, headers=admin).json()["run_id"]
        for _ in range(180):
            result = call("GET", "/admin/ingestion/runs/" + rescan, headers=admin).json()
            if result["status"] in ("completed", "completed_with_errors", "failed"):
                break
            time.sleep(2)
        report["rescan"] = result
        assert result["status"] == "completed" and not result["failed_count"], result
        _, after, _ = snapshot(cid, rescan)
        assert len(after) == before
        passed("unchanged rescan preserves canonical document count")
        for h in (user, admin):
            call("POST", "/auth/logout", headers=h, expected=204)
            call("GET", "/auth/me", headers=h, expected=401)
        passed("revoked sessions rejected")
    with database_engine("audit").connect() as c:
        actions = {r[0] for r in c.execute(text("SELECT action FROM audit_events WHERE actor=:id"), {"id": account["id"]})}
    assert {"SEARCH", "FILE_PREVIEW", "DOWNLOAD_DELIVERY_STARTED"} <= actions, actions
    passed("operations persist in Audit")
    report["finished_at"] = time.time()
    report["status"] = "passed_with_limitations" if report["limitations"] else "passed"
    save()
    print("REPORT", str(output), flush=True)


if __name__ == "__main__":
    main()

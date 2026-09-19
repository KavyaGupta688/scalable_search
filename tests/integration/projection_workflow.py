"""Deterministic AI-output adapter test. This deliberately does not validate model quality."""

import os, uuid, time, json, io, zipfile
from sqlalchemy import text
from sqlalchemy.orm import Session
from qdrant_client import models
import httpx
from modules.shared.integration import database_engine
from modules.shared.vector_store import client, collection
from modules.shared.delivery import enqueue
from modules.shared.indexer import index_document
from modules.ai_tag_description_generation.app.models import (
    DocumentEnrichmentMetadata,
    EnrichmentTask,
)
from modules.ai_tag_description_generation.worker.pipeline.task_dispatcher import (
    transition_status,
)

c = httpx.Client(base_url="http://gateway:8000", timeout=90)


def call(method, path, status=200, **kw):
    if path == "/search":
        kw["json"]["filters"] = {"dataset_ids": [dataset_id]}
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
with database_engine("ingestion").connect() as conn:
    docs = [
        dict(r)
        for r in conn.execute(
            text(
                "SELECT d.*,a.id AS asset_id FROM documents d JOIN LATERAL (SELECT id FROM source_assets WHERE document_id=d.id LIMIT 1) a ON true WHERE d.source_connector_id=(SELECT id FROM connectors WHERE name LIKE 'Acceptance NAS %' ORDER BY id LIMIT 1) ORDER BY d.source_ref"
            )
        ).mappings()
    ]
assert len(docs) == 5
dataset_id = str(docs[0]["source_connector_id"])
ids = [str(d["id"]) for d in docs[:5]]
statuses = ["completed", "partial", "needs_review", "failed_terminal", "queued"]
for d, status in zip(docs, statuses):
    did = str(d["id"])
    with Session(database_engine("enrichment")) as session:
        session.merge(
            EnrichmentTask(
                document_id=did,
                status="in_progress",
                source_ref=d["source_ref"],
                source_asset_id=d["asset_id"],
                mime_type=d["mime_type"],
                size_bytes=d["size_bytes"],
                checksum_sha256=d["checksum_sha256"],
                entitlement_id=d["entitlement_id"],
            )
        )
        prior = (
            session.query(DocumentEnrichmentMetadata)
            .filter_by(
                document_id=d["id"],
                model_version="test-adapter",
                enrichment_version="test-1",
            )
            .first()
        )
        if prior is None:
            session.add(
                DocumentEnrichmentMetadata(
                    document_id=d["id"],
                    source_asset_id=d["asset_id"],
                    model_version="test-adapter",
                    enrichment_version="test-1",
                    generated_tags=[{"tag": "acceptance"}],
                    short_description="Acceptance deterministic adapter output",
                    privacy_safety_labels={
                        "contains_pii": False,
                        "nsfw_flagged": False,
                        "analysis_incomplete": False,
                    },
                    status=status,
                )
            )
        session.commit()
    client().upsert(
        collection(),
        points=[
            models.PointStruct(
                id=did,
                vector=[1.0] + [0.0] * 511,
                payload={"file_id": did, "document_id": did, "published": False},
            )
        ],
        wait=True,
    )
    if status == "queued":
        with database_engine("enrichment").begin() as conn:
            conn.execute(
                text(
                    "UPDATE enrichment_tasks SET status='queued' WHERE document_id=:id"
                ),
                {"id": did},
            )
    else:
        transition_status(did, status)
    # Explicit invocation verifies projection while the same work remains durable/replayable.
    index_document(did)
    index_document(did)
email = "projection-" + uuid.uuid4().hex[:8] + "@example.com"
password = "Projection-password-123"
call(
    "POST",
    "/auth/register",
    json={"email": email, "password": password, "role": "user"},
)
u = {
    "Authorization": "Bearer "
    + call(
        "POST",
        "/auth/login",
        json={"email": email, "password": password, "role": "user"},
    ).json()["access_token"]
}
r = call(
    "POST", "/search", headers=u, json={"query": "acceptance", "search_mode": "text"}
).json()
assert {x["file_id"] for x in r["results"]} == set(ids[:2]), r
assert r["total"] == 2 and r["facets"]["total_matches"] == 2
for did in ids[2:]:
    call("GET", "/files/" + did, headers=u, status=404)
    call("POST", "/search/similar", headers=u, status=404, json={"file_id": did})
    call("POST", "/downloads/batch", headers=u, status=403, json={"file_ids": [did]})
# Publish the remaining fixtures to check packaging of all five modalities.
with database_engine("enrichment").begin() as conn:
    conn.execute(
        text(
            "UPDATE enrichment_tasks SET status='completed' WHERE document_id IN (SELECT id FROM ingestion.documents WHERE source_connector_id=:connector)"
        ),
        {"connector": dataset_id},
    )
for did in ids:
    index_document(did)
first = call(
    "POST",
    "/search",
    headers=u,
    json={"query": "acceptance", "search_mode": "text", "limit": 2, "offset": 0},
).json()
second = call(
    "POST",
    "/search",
    headers=u,
    json={"query": "acceptance", "search_mode": "text", "limit": 2, "offset": 2},
).json()
assert first["total"] == 5 and not (
    {r["file_id"] for r in first["results"]} & {r["file_id"] for r in second["results"]}
)
call("GET", "/files/" + ids[0], headers=u)
sim = call("POST", "/search/similar", headers=u, json={"file_id": ids[0]}).json()
assert ids[0] not in [r["file_id"] for r in sim["results"]]
job = call(
    "POST", "/downloads/batch", headers=u, status=202, json={"file_ids": ids}
).json()["download_id"]
for _ in range(60):
    state = call("GET", "/downloads/" + job, headers=u).json()
    if state["status"] != "building":
        break
    time.sleep(1)
assert state["status"] == "ready", state
archive = call("GET", "/downloads/" + job + "/content", headers=u).content
z = zipfile.ZipFile(io.BytesIO(archive))
assert len(z.namelist()) == 6
png = next(name for name in z.namelist() if name.endswith(".png"))
verification = call(
    "POST",
    "/downloads/forensic/verify",
    headers=h,
    files={"file": ("renamed.bin", z.read(png))},
).json()
assert verification["signature_valid"] and verification["audit_match"], verification
# Delivery must recheck the current entitlement, including a previously ready archive.
with database_engine("ingestion").begin() as conn:
    conn.execute(
        text("UPDATE license_entitlements SET status='expired' WHERE id=:id"),
        {"id": docs[0]["entitlement_id"]},
    )
try:
    call("GET", "/documents/" + ids[0] + "/content", headers=u, status=403)
    call("GET", "/downloads/" + job + "/content", headers=u, status=403)
    call("GET", "/files/" + ids[0], headers=u, status=404)
finally:
    with database_engine("ingestion").begin() as conn:
        conn.execute(
            text("UPDATE license_entitlements SET status='active' WHERE id=:id"),
            {"id": docs[0]["entitlement_id"]},
        )
print(
    json.dumps(
        {
            "verified": "deterministic projection, visibility, facets, pagination, similarity, five-modality packaging, forensic match, expiry recheck",
            "download_id": job,
        }
    )
)

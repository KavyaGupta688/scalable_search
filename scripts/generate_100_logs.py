"""
Generates 120+ realistic audit logs into the relational database (and exports them to CSV),
and generates 120+ operational server logs into server_operational.log.
"""
from datetime import datetime, timedelta, timezone
import json
import logging
import os
import random
import sys
import uuid
import csv

# Ensure root dir is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.shared.audit import record, list_persisted, ENGINE
from sqlalchemy import text

# Configure Operational Server Logger
LOG_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server_operational.log"))
CSV_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "audit_logs_100.csv"))

server_logger = logging.getLogger("srib_server")
server_logger.setLevel(logging.INFO)

# Remove old handlers to prevent duplicate outputs
for h in server_logger.handlers[:]:
    server_logger.removeHandler(h)

fh = logging.FileHandler(LOG_FILE_PATH, mode="w", encoding="utf-8")
fh.setFormatter(logging.Formatter('{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": %(message)s}'))
server_logger.addHandler(fh)

USERS = [
    ("k.sharma@samsung.com", "analyst", "BLR-CAMPUS-B3", "10.112.4.88"),
    ("j.doe@samsung.com", "analyst", "SUWON-CAMPUS-R4", "10.14.88.12"),
    ("admin.security@samsung.com", "admin", "BLR-CAMPUS-B1", "10.112.1.5"),
    ("s.park@samsung.com", "analyst", "SEOUL-RND", "10.22.105.41"),
    ("a.verma@samsung.com", "analyst", "BLR-CAMPUS-B3", "10.112.4.92"),
    ("viewer.demo@samsung.com", "viewer", "DELHI-OFFICE", "10.88.19.4"),
]

SEARCH_QUERIES = [
    ("circuit board defect detection", "Technology", 1420),
    ("5G antenna beamforming array", "Technology", 890),
    ("Samsung Galaxy S25 ultra sensor layout", "Product", 3400),
    ("autonomous vehicle LiDAR point cloud", "Vehicles", 2150),
    ("street night rainy neon lighting", "Photography", 5120),
    ("medical CT scan chest lung nodule", "Medical", 680),
    ("abstract generative 3D wave texture", "Abstract", 1890),
    ("wildlife tiger portrait Bengal forest", "Nature", 2400),
    ("office collaborative team whiteboard", "Business", 1120),
    ("classroom lecture interactive screen", "Education", 950),
    ("factory robotic arm assembly line", "Technology", 4310),
    ("drone aerial agriculture crop field", "Nature", 1750),
]

CATEGORIES = ["Technology", "People", "Nature", "Architecture", "Medical", "Vehicles", "Abstract", "Food"]

def main():
    print("=== Generating 120+ Audit Logs (Relational SQL) and Server Logs (Non-Relational Stream) ===")

    # Reset relational audit table for clean 100+ run
    with ENGINE.begin() as conn:
        conn.execute(text("DELETE FROM audit_events"))

    start_time = datetime.now(timezone.utc) - timedelta(hours=12)

    total_events = 125
    for i in range(total_events):
        curr_time = start_time + timedelta(minutes=i * 5, seconds=random.randint(1, 45))
        user_email, role, campus, ip = random.choice(USERS)
        corr_id = f"corr-{uuid.uuid4().hex[:8]}"

        event_category = random.choices(
            ["auth", "ingest", "ai", "search", "preview", "download", "retention"],
            weights=[15, 20, 20, 30, 25, 12, 3]
        )[0]

        if event_category == "auth":
            action = "auth.login"
            status = "SUCCESS"
            exec_time = random.randint(30, 80)
            meta = {"provider": "SAMSUNG_KNOX_SSO", "mfa_verified": True, "auth_domain": "CORP.SAMSUNG.NET"}
            record(
                action=action, actor=user_email, user_role=role,
                entity_type="user_session", entity_id=f"sess-{uuid.uuid4().hex[:8]}",
                status=status, location=campus, client_ip=ip, correlation_id=corr_id,
                execution_time_ms=exec_time, metadata=meta
            )
            server_logger.info(json.dumps({
                "subsystem": "auth_service", "event": "KNOX_SSO_AUTHENTICATED",
                "user": user_email, "role": role, "ip": ip, "latency_ms": exec_time
            }))

        elif event_category == "ingest":
            action = "ingestion.document.ingested"
            status = "SUCCESS"
            exec_time = random.randint(180, 500)
            doc_id = str(uuid.uuid4())
            s3_key = f"datasets/2026-batch/{random.choice(CATEGORIES).lower()}_{i:04d}.jpg"
            file_size = random.randint(2_000_000, 45_000_000)
            sha256 = uuid.uuid4().hex + uuid.uuid4().hex[:32]
            meta = {
                "connector_id": "conn-s3-prod-kr",
                "s3_bucket": "srib-data-lake-450tb",
                "s3_key": s3_key,
                "checksum_sha256": sha256,
                "size_bytes": file_size,
                "mime_type": "image/jpeg",
                "deduplication": "UNIQUE_NEW"
            }
            record(
                action=action, actor="ingestion-worker-daemon", user_role="system",
                entity_type="document", entity_id=doc_id, status=status,
                location="SRIB-BLR-DC", correlation_id=corr_id,
                execution_time_ms=exec_time, metadata=meta
            )
            server_logger.info(json.dumps({
                "subsystem": "ingestion_engine", "event": "S3_OBJECT_INGESTED",
                "doc_id": doc_id, "size_bytes": file_size, "sha256": sha256[:16], "latency_ms": exec_time
            }))

        elif event_category == "ai":
            action = "ai.enrichment.completed"
            status = "SUCCESS"
            exec_time = random.randint(800, 2200)
            doc_id = str(uuid.uuid4())
            meta = {
                "vision_model": "SigLIP2-SO400M-14",
                "vlm_captioner": "Moondream2",
                "tags_extracted": random.sample(["high-res", "raw", "outdoor", "macro", "sensor", "lens", "silicon", "lab"], 4),
                "safety_screening": {"pii_detected": False, "nsfw_detected": False},
                "confidence_score": round(random.uniform(0.92, 0.99), 3)
            }
            record(
                action=action, actor="gpu-worker-a100-cluster", user_role="system",
                entity_type="document_enrichment_metadata", entity_id=doc_id, status=status,
                location="SRIB-BLR-DC", correlation_id=corr_id,
                execution_time_ms=exec_time, metadata=meta
            )
            server_logger.info(json.dumps({
                "subsystem": "ai_inference", "event": "GPU_MULTIMODAL_PASS_COMPLETE",
                "doc_id": doc_id, "model": "SigLIP2", "latency_ms": exec_time, "gpu_util_pct": random.randint(70, 95)
            }))

        elif event_category == "search":
            action = "search.query"
            status = "SUCCESS"
            exec_time = random.randint(120, 350)
            query_tuple = random.choice(SEARCH_QUERIES)
            query_text = query_tuple[0]
            hits = query_tuple[2] + random.randint(-50, 100)
            meta = {
                "search_mode": "hybrid_semantic_fts",
                "result_count": hits,
                "filters": {"category": query_tuple[1], "resolution": ">=1080p"},
                "page": 1, "page_size": 50
            }
            record(
                action=action, actor=user_email, user_role=role,
                entity_type="search_session", entity_id=f"search-{uuid.uuid4().hex[:8]}",
                status=status, query=query_text, location=campus, client_ip=ip,
                correlation_id=corr_id, execution_time_ms=exec_time, metadata=meta
            )
            server_logger.info(json.dumps({
                "subsystem": "search_service", "event": "VECTOR_HYBRID_QUERY",
                "user": user_email, "query": query_text, "hits": hits, "qdrant_latency_ms": exec_time
            }))

        elif event_category == "preview":
            action = "document.preview"
            status = "SUCCESS"
            exec_time = random.randint(40, 120)
            doc_id = str(uuid.uuid4())
            meta = {
                "preview_format": "webp_lossless",
                "resolution": "1920x1080",
                "zoom_factor": random.choice([1.0, 1.5, 2.0, 4.0])
            }
            record(
                action=action, actor=user_email, user_role=role,
                entity_type="document", entity_id=doc_id, status=status,
                location=campus, client_ip=ip, correlation_id=corr_id,
                execution_time_ms=exec_time, metadata=meta
            )
            server_logger.info(json.dumps({
                "subsystem": "preview_cache", "event": "THUMBNAIL_DELIVERED",
                "doc_id": doc_id, "user": user_email, "cached": True, "latency_ms": exec_time
            }))

        elif event_category == "download":
            action = "download.watermark.injected"
            status = "SUCCESS"
            exec_time = random.randint(500, 1500)
            file_count = random.randint(10, 150)
            batch_id = f"batch-dl-{uuid.uuid4().hex[:8]}"
            token_sig = uuid.uuid4().hex + uuid.uuid4().hex
            meta = {
                "file_count": file_count,
                "total_bytes": file_count * random.randint(5_000_000, 20_000_000),
                "forensic_signature": token_sig,
                "watermark_algorithm": "HMAC-SHA256-STEGANO",
                "archive_format": "application/zip"
            }
            record(
                action=action, actor=user_email, user_role=role,
                entity_type="download_batch", entity_id=batch_id, status=status,
                location=campus, client_ip=ip, correlation_id=corr_id,
                execution_time_ms=exec_time, metadata=meta
            )
            server_logger.info(json.dumps({
                "subsystem": "download_worker", "event": "ZIP_BUNDLE_WATERMARKED",
                "batch_id": batch_id, "files": file_count, "token_sig": token_sig[:16], "latency_ms": exec_time
            }))

        elif event_category == "retention":
            action = "retention.purge.executed"
            status = "SUCCESS"
            exec_time = random.randint(2500, 4800)
            entitlement_id = f"entitlement-vendor-{random.randint(2022, 2025)}"
            reclaimed_gb = round(random.uniform(50.0, 600.0), 1)
            files_purged = int(reclaimed_gb * 100)
            meta = {
                "policy_code": "PURGE_IMMEDIATE_POST_EXPIRY",
                "reclaimed_gb": reclaimed_gb,
                "purged_files": files_purged,
                "sla_compliance": "< 24 hours verified",
                "verification_hash": uuid.uuid4().hex + uuid.uuid4().hex
            }
            record(
                action=action, actor="retention-compliance-daemon", user_role="system",
                entity_type="license_entitlement", entity_id=entitlement_id, status=status,
                location="SRIB-BLR-DC", correlation_id=corr_id,
                execution_time_ms=exec_time, metadata=meta
            )
            server_logger.warning(json.dumps({
                "subsystem": "retention_daemon", "event": "LICENSE_EXPIRY_PURGE_COMPLETE",
                "entitlement": entitlement_id, "files_purged": files_purged, "reclaimed_gb": reclaimed_gb, "sla": "PASSED"
            }))

    # Query all events from relational DB
    all_persisted = list_persisted(limit=500)
    print(f"Successfully committed {len(all_persisted)} events into Relational Table 'audit_events'.")

    # Export to CSV
    with open(CSV_FILE_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "event_id", "action", "actor", "user_role", "entity_type", "entity_id",
            "status", "occurred_at", "query", "device_code", "location_code",
            "client_ip", "correlation_id", "execution_time_ms", "metadata_json"
        ])
        for r in all_persisted:
            writer.writerow([
                r["event_id"], r["action"], r["actor"], r["user_role"],
                r["entity_type"], r["entity_id"], r["status"], r["occurred_at"].isoformat(),
                r["query"] or "", r["device_code"] or "", r["location_code"] or "",
                r["client_ip"] or "", r["correlation_id"] or "", r["execution_time_ms"],
                json.dumps(r["metadata"])
            ])

    print(f"Exported {len(all_persisted)} records to CSV file: {CSV_FILE_PATH}")
    print(f"Generated 125 structured operational server log lines to: {LOG_FILE_PATH}")

if __name__ == "__main__":
    main()

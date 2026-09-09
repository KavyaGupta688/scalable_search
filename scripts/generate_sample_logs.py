"""
Generates real audit events in the relational database and operational server logs in both JSON and text format.
"""
from datetime import datetime, timezone
import json
import logging
import os
import sys

# Ensure root dir is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.shared.audit import record, list_persisted

# Configure Operational Server Logger
LOG_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server_operational.log"))

server_logger = logging.getLogger("srib_platform")
server_logger.setLevel(logging.INFO)

# File handler
fh = logging.FileHandler(LOG_FILE_PATH, mode="a", encoding="utf-8")
formatter = logging.Formatter('{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": %(message)s}')
fh.setFormatter(formatter)
server_logger.addHandler(fh)

# Console handler
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
server_logger.addHandler(ch)

def emit_server_log(level: str, event_type: str, message: str, **kwargs):
    payload = json.dumps({"event_type": event_type, "msg": message, **kwargs})
    if level.upper() == "INFO":
        server_logger.info(payload)
    elif level.upper() == "WARNING":
        server_logger.warning(payload)
    elif level.upper() == "ERROR":
        server_logger.error(payload)

def main():
    print("=== Generating Structured Audit Logs & Server Logs ===")

    # 1. Ingestion Event
    emit_server_log("INFO", "INGEST_DISCOVER", "Connector S3-Vendor-KR discovered 1 new object", connector_id="conn-s3-kr-01", s3_key="batch_001/samsung_processor_042.jpg", size_bytes=14680064)
    audit_ingest = record(
        action="ingestion.document.ingested",
        actor="system-ingestion-worker-01",
        user_role="system",
        entity_type="document",
        entity_id="doc-uuid-4491-a1b2",
        status="SUCCESS",
        location="SRIB-BLR-DC",
        correlation_id="trace-ingest-8812",
        execution_time_ms=315,
        metadata={
            "connector_name": "S3-Vendor-KR",
            "s3_bucket": "sr-kr-shutterstock-kms",
            "source_ref": "batch_001/samsung_processor_042.jpg",
            "checksum_sha256": "4a5c0b8921cf0012e84126bb024982a392110cfa018247df60341829eebf4019",
            "size_bytes": 14680064,
            "mime_type": "image/jpeg",
            "deduplication": "UNIQUE_NEW"
        }
    )
    print(f"Recorded Audit Event: {audit_ingest['event_id']} ({audit_ingest['action']})")

    # 2. AI Enrichment Event
    emit_server_log("INFO", "AI_ENRICH_INFERENCE", "GPU worker completed multi-modal inference", model="SigLIP2-SO400M-14", doc_id="doc-uuid-4491-a1b2", latency_ms=1420)
    audit_ai = record(
        action="ai.enrichment.completed",
        actor="worker-gpu-a100-node2",
        user_role="system",
        entity_type="document_enrichment_metadata",
        entity_id="doc-uuid-4491-a1b2",
        status="SUCCESS",
        location="SRIB-BLR-DC",
        correlation_id="trace-ai-7721",
        execution_time_ms=1420,
        metadata={
            "model_version": "SigLIP2-SO400M-14",
            "captioner": "Moondream2",
            "generated_tags": ["semiconductor", "processor", "chip", "testbench", "circuit board"],
            "safety_screening": {"pii_detected": False, "nsfw_detected": False},
            "quality_score": 0.984
        }
    )
    print(f"Recorded Audit Event: {audit_ai['event_id']} ({audit_ai['action']})")

    # 3. User Authentication
    emit_server_log("INFO", "AUTH_LOGIN", "Knox SSO authentication verified for user k.sharma@samsung.com", role="analyst", client_ip="10.112.4.88")
    audit_login = record(
        action="auth.login",
        actor="k.sharma@samsung.com",
        user_role="analyst",
        entity_type="user_session",
        entity_id="sess-889104",
        status="SUCCESS",
        device="workstation-laptop-blr-04",
        location="BLR-CAMPUS-B3",
        client_ip="10.112.4.88",
        correlation_id="trace-auth-1029",
        execution_time_ms=45,
        metadata={"sso_provider": "KNOX_SSO", "mfa": True}
    )
    print(f"Recorded Audit Event: {audit_login['event_id']} ({audit_login['action']})")

    # 4. Search Query
    emit_server_log("INFO", "SEARCH_EXECUTE", "Hybrid vector + FTS query executed across 496,000 assets", query="semiconductor chip testbench", hits=4218, latency_ms=210)
    audit_search = record(
        action="search.query",
        actor="k.sharma@samsung.com",
        user_role="analyst",
        entity_type="search_session",
        entity_id="search-uuid-9941",
        status="SUCCESS",
        query="semiconductor chip testbench",
        device="workstation-laptop-blr-04",
        location="BLR-CAMPUS-B3",
        client_ip="10.112.4.88",
        correlation_id="trace-search-5520",
        execution_time_ms=210,
        metadata={
            "search_mode": "hybrid_vector_keyword",
            "result_count": 4218,
            "filters": {"category": "Technology", "resolution": ">=1080p"}
        }
    )
    print(f"Recorded Audit Event: {audit_search['event_id']} ({audit_search['action']})")

    # 5. Preview Document
    emit_server_log("INFO", "PREVIEW_MODAL", "Serving high-resolution preview modal", doc_id="doc-uuid-4491-a1b2", user="k.sharma@samsung.com")
    audit_preview = record(
        action="document.preview",
        actor="k.sharma@samsung.com",
        user_role="analyst",
        entity_type="document",
        entity_id="doc-uuid-4491-a1b2",
        status="SUCCESS",
        device="workstation-laptop-blr-04",
        location="BLR-CAMPUS-B3",
        client_ip="10.112.4.88",
        correlation_id="trace-prev-1194",
        execution_time_ms=85,
        metadata={"preview_format": "webp_lossless", "viewport": "1920x1080"}
    )
    print(f"Recorded Audit Event: {audit_preview['event_id']} ({audit_preview['action']})")

    # 6. Batch Download & Forensic Watermarking
    emit_server_log("INFO", "CELERY_DOWNLOAD_START", "Celery worker building selective ZIP bundle", job_id="job-dl-9921", total_files=120)
    emit_server_log("INFO", "FORENSIC_WATERMARK_INJECTED", "HMAC-SHA256 cryptographic watermark embedded", job_id="job-dl-9921", token_sig="e5b7c89a01f6d3329910a30b42f38d17c918f0a41d0172e811cba10245a901ff")
    audit_download = record(
        action="download.watermark.injected",
        actor="k.sharma@samsung.com",
        user_role="analyst",
        entity_type="download_batch",
        entity_id="batch-dl-9921",
        status="SUCCESS",
        device="workstation-laptop-blr-04",
        location="BLR-CAMPUS-B3",
        client_ip="10.112.4.88",
        correlation_id="trace-dl-3341",
        execution_time_ms=640,
        metadata={
            "total_files": 120,
            "bundle_size_bytes": 2576980377,
            "token_signature": "e5b7c89a01f6d3329910a30b42f38d17c918f0a41d0172e811cba10245a901ff",
            "steganographic_key": "SRIB-DL-2026",
            "format": "application/zip"
        }
    )
    print(f"Recorded Audit Event: {audit_download['event_id']} ({audit_download['action']})")

    # 7. Compliance License Purge
    emit_server_log("WARNING", "COMPLIANCE_PURGE_START", "Executing automated SLA purge for expired license", entitlement_id="entitlement-shutterstock-2024-kr")
    emit_server_log("INFO", "COMPLIANCE_PURGE_FINISH", "Successfully unlinked 48,200 files and reclaimed 482.4 GB", reclaimed_gb=482.4, purge_status="COMPLIANT_UNDER_24H")
    audit_purge = record(
        action="retention.purge.executed",
        actor="compliance-daemon",
        user_role="system",
        entity_type="license_entitlement",
        entity_id="entitlement-shutterstock-2024-kr",
        status="SUCCESS",
        location="SRIB-BLR-DC",
        correlation_id="trace-retention-0091",
        execution_time_ms=3890,
        metadata={
            "files_purged": 48200,
            "storage_reclaimed_gb": 482.4,
            "sla_compliance": "< 24 hours verified",
            "verification_checksum": "a9012f45c810bbf482310de456819a0f01192834bcee58921a4f001289de6102"
        }
    )
    print(f"Recorded Audit Event: {audit_purge['event_id']} ({audit_purge['action']})")

    print("\n=== Generation Complete ===")
    print(f"Total Audit Events in Relational Ledger: {len(list_persisted())}")
    print(f"Operational Server Log file created at: {LOG_FILE_PATH}")

if __name__ == "__main__":
    main()

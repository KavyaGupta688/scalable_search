-- ============================================================================
-- Data Ingestion Module — Initial Schema Migration
-- Version: 001
-- Description: Creates the core tables for connectors, documents, and
--              enumeration checkpoints.
--
-- BACKUP NOTE: The database should be backed up using the organization's
-- existing backup infrastructure. This module does not include its own
-- backup logic. Ensure regular pg_dump or continuous archiving (WAL)
-- is configured by your DBA team before going to production.
-- ============================================================================

BEGIN;

-- ─── Connectors ─────────────────────────────────────────────────────────────
-- Each row represents a configured data source (S3 bucket or NAS share).
-- Credentials are stored in HashiCorp Vault; only the vault path is here.

CREATE TABLE connectors (
    id              UUID PRIMARY KEY,
    name            TEXT NOT NULL,
    source_type     TEXT NOT NULL CHECK (source_type IN ('S3', 'NAS_SMB', 'NAS_NFS')),
    endpoint_url    TEXT,
    bucket          TEXT,
    mount_path      TEXT,
    addressing_style TEXT,
    signature_version TEXT,
    secret_path     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'unverified'
                        CHECK (status IN ('verified', 'unverified', 'failed')),
    created_by      UUID NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_verified_at TIMESTAMPTZ
);

-- ─── Documents ──────────────────────────────────────────────────────────────
-- Canonical metadata record for every unique ingested file.
-- One row per unique SHA-256 checksum.

CREATE TABLE documents (
    id                  UUID PRIMARY KEY,
    checksum_sha256     TEXT NOT NULL,
    size_bytes          BIGINT NOT NULL,
    mime_type           TEXT NOT NULL,
    storage_path        TEXT NOT NULL,
    source_connector_id UUID REFERENCES connectors(id),
    source_ref          TEXT NOT NULL,
    created_by          UUID,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    tika_metadata       JSONB
);

CREATE UNIQUE INDEX idx_documents_checksum ON documents (checksum_sha256);
CREATE INDEX idx_documents_mime_type ON documents (mime_type);
CREATE INDEX idx_documents_source_connector ON documents (source_connector_id);
CREATE INDEX idx_documents_created_at ON documents (created_at);

-- ─── Duplicate Links ────────────────────────────────────────────────────────
-- Lightweight link record created when a file's SHA-256 matches an existing
-- document. No second copy is stored in MinIO.

CREATE TABLE duplicate_links (
    id                      UUID PRIMARY KEY,
    original_document_id    UUID NOT NULL REFERENCES documents(id),
    source_connector_id     UUID NOT NULL REFERENCES connectors(id),
    source_ref              TEXT NOT NULL,
    detected_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_duplinks_original ON duplicate_links (original_document_id);
CREATE INDEX idx_duplinks_source_ref ON duplicate_links (source_ref);

-- ─── Enumeration Checkpoints ────────────────────────────────────────────────
-- Persists the last enumeration position per connector so a crash mid-scan
-- resumes instead of re-scanning from zero.

CREATE TABLE enumeration_checkpoints (
    connector_id        UUID PRIMARY KEY REFERENCES connectors(id),
    continuation_token  TEXT,
    last_scanned_path   TEXT,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;

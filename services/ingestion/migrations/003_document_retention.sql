-- Historical reference SQL equivalent of Alembic revision 003.
-- Revision 004 finalizes Option A and supersedes these prototype column names.
-- Apply through `alembic upgrade head`; do not run this SQL manually.
ALTER TABLE documents ADD COLUMN ingested_at timestamptz;
ALTER TABLE documents ADD COLUMN expires_at timestamptz;
ALTER TABLE documents ADD COLUMN retention_policy_years integer NOT NULL DEFAULT 3;
ALTER TABLE documents ADD COLUMN object_version_id text;
ALTER TABLE documents ADD COLUMN retention_status varchar(32) NOT NULL DEFAULT 'active';
ALTER TABLE documents ADD COLUMN object_deleted_at timestamptz;
ALTER TABLE documents ADD COLUMN retention_last_checked_at timestamptz;
ALTER TABLE documents ADD COLUMN retention_last_error text;
ALTER TABLE documents ADD COLUMN lifecycle_rule_id text;
ALTER TABLE documents ADD COLUMN lifecycle_outcome varchar(64) NOT NULL DEFAULT 'pending';

UPDATE documents
SET ingested_at = created_at,
    expires_at = created_at + INTERVAL '3 years'
WHERE ingested_at IS NULL OR expires_at IS NULL;

ALTER TABLE documents ALTER COLUMN ingested_at SET NOT NULL;
ALTER TABLE documents ALTER COLUMN expires_at SET NOT NULL;
ALTER TABLE documents ADD CONSTRAINT ck_documents_retention_status
  CHECK (retention_status IN ('active', 'deleted', 'missing', 'blocked', 'error'));
ALTER TABLE documents ADD CONSTRAINT ck_documents_retention_window
  CHECK (expires_at >= ingested_at);
CREATE INDEX idx_documents_retention_due ON documents (retention_status, expires_at);

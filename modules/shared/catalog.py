"""Authoritative read-access policy; cached payloads cannot grant access."""

from fastapi import HTTPException
from sqlalchemy import text, bindparam
from modules.shared.integration import database_engine

VISIBLE_SQL = """EXISTS (
    SELECT 1 FROM ingestion.documents d
    JOIN ingestion.license_entitlements e ON e.id=d.entitlement_id
    JOIN enrichment.enrichment_tasks t ON t.document_id=d.id
    WHERE d.id::text=file_metadata.file_id AND e.status='active' AND e.expires_at>now()
    AND t.status IN ('completed','partial') AND file_metadata.published=true
)"""


def require_downloadable(ids: list[str]):
    if not ids:
        raise HTTPException(400, "No documents selected")
    statement = text(
        "SELECT file_id FROM search.file_metadata AS file_metadata WHERE file_id IN :ids AND "
        + VISIBLE_SQL
    ).bindparams(bindparam("ids", expanding=True))
    with database_engine("search").connect() as conn:
        allowed = set(conn.execute(statement, {"ids": ids}).scalars())
    if allowed != set(ids):
        raise HTTPException(
            403, "One or more documents are unavailable, expired, or awaiting review"
        )

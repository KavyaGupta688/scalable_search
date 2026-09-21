"""Measure pixel size / duration for media enriched before the AI pipeline stored them.

Resolution filters need width and height, and ingestion drops vendor width/height, so files
enriched earlier have none. This measures those files again from their source bytes, stores
the result in the enrichment record (quality_labels.technical) and re-indexes the document
so Search and Qdrant pick it up. New enrichments capture this automatically.

Dry run by default (lists what is missing, downloads nothing):

    python scripts/backfill_media_dimensions.py
    python scripts/backfill_media_dimensions.py --apply [--limit 200]

Run it in the AI worker's environment: the ingestion API must be reachable and
DATABASE_URL_SYNC / QDRANT_URL set. Files above the worker's MAX_SOURCE_BYTES are reported
as failed and skipped, exactly as enrichment skips them.
"""

import argparse
import json
import sys
from pathlib import Path

CANDIDATES = """
SELECT file_id, mime_type FROM file_metadata
WHERE published AND (
    (file_type IN ('image', 'video') AND (width IS NULL OR height IS NULL))
    OR (file_type IN ('audio', 'video') AND duration IS NULL))
ORDER BY file_id LIMIT :limit
"""

STORE = """
UPDATE document_enrichment_metadata
SET quality_labels = jsonb_set(coalesce(quality_labels, '{}'::jsonb), '{technical}', CAST(:technical AS jsonb)),
    updated_at = now()
WHERE id = (SELECT id FROM document_enrichment_metadata
            WHERE document_id = CAST(:document_id AS uuid) ORDER BY updated_at DESC, id LIMIT 1)
"""


def backfill(rows, *, materialize, probe, store, reindex):
    """Measure, store and re-index each (document_id, mime_type). One failure never stops the run."""
    result = {"measured": 0, "unmeasurable": 0, "failed": 0, "errors": []}
    for document_id, mime_type in rows:
        try:
            with materialize(document_id) as path:
                technical = probe(path, mime_type)
            if not technical:
                result["unmeasurable"] += 1
                continue
            store(document_id, technical)
            reindex(document_id)
            result["measured"] += 1
        except Exception as exc:  # noqa: BLE001 - report and continue with the next file
            result["failed"] += 1
            result["errors"].append((document_id, f"{type(exc).__name__}: {str(exc)[:200]}"))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="measure, store and re-index (default: dry run)")
    parser.add_argument("--limit", type=int, default=200, help="maximum files per run (default 200)")
    args = parser.parse_args(argv)

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from sqlalchemy import text
    from modules.shared.integration import database_engine

    with database_engine("search").connect() as connection:
        rows = [tuple(row) for row in connection.execute(text(CANDIDATES), {"limit": args.limit})]
    print(f"{len(rows)} published file(s) are missing measured dimensions or duration.")
    if not args.apply:
        print("Dry run: nothing downloaded or changed. Re-run with --apply.")
        return 0

    from modules.ai_tag_description_generation.app.ingestion_client import get_document, materialize_document
    from modules.ai_tag_description_generation.worker.pipeline.technical_metadata import probe
    from modules.shared.indexer import index_document

    enrichment = database_engine("enrichment")

    def store(document_id, technical):
        with enrichment.begin() as connection:
            connection.execute(text(STORE), {"document_id": document_id, "technical": json.dumps(technical)})

    result = backfill(
        rows,
        materialize=lambda document_id: materialize_document(get_document(document_id)),
        probe=probe,
        store=store,
        reindex=index_document,
    )
    print(f"measured and re-indexed: {result['measured']}, unmeasurable: {result['unmeasurable']}, failed: {result['failed']}")
    for document_id, message in result["errors"]:
        print(f"  {document_id}: {message}")
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())

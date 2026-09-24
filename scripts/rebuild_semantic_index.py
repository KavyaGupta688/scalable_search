"""Build the separate v2 index without modifying legacy vectors or canonical records.
Run inside the configured search runtime: python scripts/rebuild_semantic_index.py.
"""
import json
import argparse
from modules.shared.semantic_index import provision, index_file
from modules.shared.vector_store import client, collection
from modules.shared.integration import database_engine
from sqlalchemy import text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="/tmp/semantic-index-report.json")
    parser.add_argument("--text-only", action="store_true")
    parser.add_argument("--retry-missing-visuals", action="store_true")
    parser.add_argument("--max-source-bytes", type=int, help="Optional maintenance batch selector; not a download limit")
    args = parser.parse_args()
    provision()
    with database_engine("search").connect() as conn:
        rows = [dict(row) for row in conn.execute(text("SELECT * FROM search.file_metadata WHERE published ORDER BY file_id")).mappings()]
    from modules.ai_tag_description_generation.app.ingestion_client import get_document, materialize_document
    from modules.ai_tag_description_generation.app.config import settings
    settings.INGESTION_REQUEST_TIMEOUT_SECONDS = 15
    settings.INGESTION_DOWNLOAD_TIMEOUT_SECONDS = 90
    report = []
    if args.retry_missing_visuals:
        from pathlib import Path
        if Path(args.report).exists():
            report = json.loads(Path(args.report).read_text())
    if args.retry_missing_visuals:
        from modules.shared.semantic_index import collection_name
        current, _ = client().scroll(collection_name(), limit=10000, with_payload=True)
        pending = {str(p.id) for p in current if p.payload.get("visual_status") == "unavailable"}
        rows = [row for row in rows if row["file_id"] in pending]
    if args.max_source_bytes is not None:
        rows = [row for row in rows if row["file_size"] <= args.max_source_bytes]
    for row in rows:
        legacy = client().retrieve(collection(), ids=[row["file_id"]], with_payload=True)
        if not legacy:
            raise RuntimeError("Missing legacy publication payload for " + row["file_id"])
        payload = legacy[0].payload
        error = None
        visual = row["mime_type"].startswith(("image/", "video/")) and not args.text_only
        if visual:
            try:
                document = get_document(row["file_id"])
                with materialize_document(document) as path:
                    status = index_file(row["file_id"], row, payload, path, row["mime_type"])
            except Exception as exc:
                # Never log signed source URLs or credentials. Preserve text retrieval.
                error = type(exc).__name__
                status = index_file(row["file_id"], row, payload, mime_type=row["mime_type"], visual_error=error)
        else:
            status = index_file(row["file_id"], row, payload, mime_type=row["mime_type"])
        report = [entry for entry in report if entry["id"] != row["file_id"]]
        report.append({"id": row["file_id"], "title": row["title"], "visual_status": status, "error": error})
        print(json.dumps(report[-1]), flush=True)
        with open(args.report, "w") as output:
            json.dump(report, output, indent=2)
    print("Indexed", len(report), "files; visual", sum(r["visual_status"] == "indexed" for r in report), flush=True)


if __name__ == "__main__":
    main()

"""Backfill the Qdrant payload fields Search filters on (licence status, size, long edge).

Points indexed before these fields existed lack them. Licence status is safe without a
backfill (the filter lets points without it through, and SQL verifies every hit), but
size and resolution filtering inside Qdrant must stay off until this has run:

    python scripts/reindex_search_payloads.py
    # then set QDRANT_EXTENDED_PAYLOAD=true for the Search service

Only payload fields are written; vectors are untouched. Safe to re-run.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qdrant_client import models  # noqa: E402
from sqlalchemy import text  # noqa: E402

from modules.shared import semantic_index  # noqa: E402
from modules.shared.indexer import _long_edge, bump_catalog_version  # noqa: E402
from modules.shared.integration import database_engine, point_id  # noqa: E402
from modules.shared.vector_store import client, collection, resolve  # noqa: E402

ROWS = text(
    """SELECT fm.file_id, fm.file_size, fm.width, fm.height, e.status
    FROM file_metadata fm
    JOIN ingestion.documents d ON d.id::text = fm.file_id
    JOIN ingestion.license_entitlements e ON e.id = d.entitlement_id
    WHERE fm.file_id > :last ORDER BY fm.file_id LIMIT :batch"""
)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--batch", type=int, default=500)
    args = parser.parse_args()

    q = client()
    targets = [name for name in (collection(), semantic_index.collection_name())
               if resolve(q, name) is not None]
    last, updated = "", 0
    while True:
        with database_engine("search").connect() as conn:
            rows = conn.execute(ROWS, {"last": last, "batch": args.batch}).all()
        if not rows:
            break
        last = rows[-1][0]
        payloads = {
            point_id(file_id): {
                "license_status": status,
                "file_size": int(size) if size is not None else None,
                "long_edge": _long_edge(width, height),
            }
            for file_id, size, width, height, status in rows
        }
        for name in targets:
            existing = [str(p.id) for p in q.retrieve(name, ids=list(payloads), with_payload=False)]
            if existing:
                q.batch_update_points(
                    name,
                    update_operations=[
                        models.SetPayloadOperation(
                            set_payload=models.SetPayload(payload=payloads[pid], points=[pid])
                        )
                        for pid in existing
                    ],
                    wait=True,
                )
        updated += len(rows)
        print(f"  {updated} documents", flush=True)
    bump_catalog_version()
    print(f"Backfilled {updated} documents in {', '.join(targets) or 'no collections'}. "
          "QDRANT_EXTENDED_PAYLOAD=true may now be set for Search.")


if __name__ == "__main__":
    main()

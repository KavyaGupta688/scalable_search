"""Move a Qdrant collection to the configured layout (shards, replication, HNSW, quantisation).

Shard count and most layout settings are fixed when a collection is created, so a layout
change means building a new physical collection and switching an alias to it. Vectors and
payloads are copied point for point; nothing is re-embedded.

    python scripts/migrate_vector_collection.py --target semantic            # copy only
    python scripts/migrate_vector_collection.py --target semantic --switch   # copy, then switch

Layout comes from QDRANT_SHARD_NUMBER, QDRANT_REPLICATION_FACTOR, QDRANT_HNSW_* and
QDRANT_QUANTIZATION (see modules/shared/vector_store.layout_config).

The first switch of a name that is still a physical collection must delete that collection
before the alias can take its name; this needs --delete-source and a typed confirmation,
and requests fail for the moment between the two steps. Later switches are atomic.

Writes made to the old collection during the copy are caught up by a second pass just
before switching (points are upserted, so repeating is safe). Run it in a quiet period,
and afterwards run scripts/reindex_search_payloads.py to refresh payloads.
"""

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qdrant_client import models  # noqa: E402

from modules.shared import semantic_index  # noqa: E402
from modules.shared.vector_store import (  # noqa: E402
    PAYLOAD_INDEXES,
    client,
    collection,
    ensure_payload_indexes,
    layout_config,
    resolve,
)


def copy_points(q, source, target, batch):
    copied, offset = 0, None
    while True:
        points, offset = q.scroll(
            source, limit=batch, offset=offset, with_payload=True, with_vectors=True
        )
        if points:
            q.upsert(
                target,
                points=[
                    models.PointStruct(id=p.id, vector=p.vector, payload=p.payload or {})
                    for p in points
                ],
                wait=True,
            )
            copied += len(points)
            print(f"  copied {copied}", flush=True)
        if offset is None:
            return copied


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--target", choices=["clip", "semantic"], required=True)
    parser.add_argument("--batch", type=int, default=256)
    parser.add_argument("--switch", action="store_true", help="point the alias at the new collection")
    parser.add_argument("--delete-source", action="store_true",
                        help="allow deleting a physical collection that holds the alias name")
    args = parser.parse_args()

    q = client()
    name = semantic_index.collection_name() if args.target == "semantic" else collection()
    indexes = semantic_index.payload_indexes() if args.target == "semantic" else PAYLOAD_INDEXES
    source = resolve(q, name)
    if source is None:
        raise SystemExit(f"Collection or alias '{name}' does not exist")
    params = q.get_collection(source).config.params
    layout = layout_config()
    target = f"{name}__s{layout['shard_number']}_{time.strftime('%Y%m%d%H%M%S')}"

    print(f"Creating {target} from {source} with {layout['shard_number']} shards, "
          f"replication {layout['replication_factor']}")
    q.create_collection(
        target,
        vectors_config=params.vectors,
        sparse_vectors_config=params.sparse_vectors,
        **layout,
    )
    ensure_payload_indexes(q, target, indexes)
    copied = copy_points(q, source, target, args.batch)
    source_count = q.count(source, exact=True).count
    target_count = q.count(target, exact=True).count
    print(f"Copied {copied}; source has {source_count}, target has {target_count}")
    if not args.switch:
        print(f"Not switched. Re-run with --switch, or delete {target} if unwanted.")
        return

    print("Catch-up pass for writes made during the copy")
    copy_points(q, source, target, args.batch)
    if q.count(target, exact=True).count < q.count(source, exact=True).count:
        raise SystemExit("Target has fewer points than source; not switching")

    if source == name:
        # The name is a physical collection; an alias cannot share its name.
        if not args.delete_source:
            raise SystemExit(f"'{name}' is a physical collection. Re-run with --delete-source "
                             "to delete it and create the alias in its place.")
        if input(f"Type '{name}' to delete it and switch: ").strip() != name:
            raise SystemExit("Not confirmed")
        q.delete_collection(name)
        q.update_collection_aliases(change_aliases_operations=[
            models.CreateAliasOperation(create_alias=models.CreateAlias(
                collection_name=target, alias_name=name)),
        ])
    else:
        # Atomic: readers see either the old or the new collection, never neither.
        q.update_collection_aliases(change_aliases_operations=[
            models.DeleteAliasOperation(delete_alias=models.DeleteAlias(alias_name=name)),
            models.CreateAliasOperation(create_alias=models.CreateAlias(
                collection_name=target, alias_name=name)),
        ])
        print(f"Old collection {source} kept; delete it once the new one is verified.")
    print(f"Alias {name} -> {target}")


if __name__ == "__main__":
    main()

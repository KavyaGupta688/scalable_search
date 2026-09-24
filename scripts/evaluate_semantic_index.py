"""Offline relevance check against an indexed catalog snapshot; no source access."""
import json
import time
from types import SimpleNamespace
from modules.shared.vector_store import client, collection
from modules.shared.semantic_index import collection_name
from app.services.vector_search_service import VectorSearchService
from app.clients.embedding_client import EmbeddingClient
from app.services.relevance_service import rerank
from app.utils.rrf import FusionResult


def main():
    q = client()
    points, _ = q.scroll(collection_name(), limit=1000, with_payload=True)
    # The rebuild report is the captured canonical title mapping.
    with open("/tmp/semantic-index-report.json") as source:
        titles = {r["id"]: r["title"] for r in json.load(source)}
    files = {str(p.id): SimpleNamespace(title=titles[str(p.id)], description=" ".join(p.payload["passages"]),
             file_name="", caption="") for p in points}
    service = VectorSearchService(q, EmbeddingClient())
    cases = {
        "dog": ["Golden Retriever Playing With Red Ball", "Responsible Dog Care Guide"],
        "canine": ["Golden Retriever Playing With Red Ball", "Responsible Dog Care Guide"],
        "man": ["Friends Playing Outdoor Basketball", "Conversation: Joy"],
        "person walking": ["Rainy City Street With Yellow Taxi"],
        "bread": ["Artisan Bakery Bread Counter"],
        "baked goods": ["Artisan Bakery Bread Counter"],
        "basketball": ["Friends Playing Outdoor Basketball"],
        "red ball": ["Golden Retriever Playing With Red Ball"],
        "snowy cabin": ["Snowy Cabin In Pine Forest"],
        "winter cottage": ["Snowy Cabin In Pine Forest"],
        "train": ["Duplicate Passenger Train"],
        "pizza": ["Fresh Vegetable Pizza"],
        "car maintenance": ["Car Maintenance Schedule"],
        "phishing protection": ["Cybersecurity Risk Brief"],
        "customer complaint": ["Customer Complaint Response Guide"],
        "quantum cryptography": [], "zzxqvbnm": [],
    }
    report = []
    for query, expected in cases.items():
        start = time.monotonic()
        raw, _ = service._retrieve_multimodal(query, list(files), 200, 0)
        fused = [FusionResult(id=r.id, rrf_score=r.raw_score,
            semantic_similarity=r.metadata.get("text_similarity"), visual_similarity=r.metadata.get("visual_similarity"),
            matched_passage=r.metadata.get("matched_passage")) for r in raw]
        results = rerank(query, fused, files)
        found = [files[r.id].title for r in results]
        row = {"query": query, "expected": expected, "top5": found[:5], "count": len(found),
            "passed": all(title in found[:5] for title in expected) if expected else not found,
            "seconds": round(time.monotonic()-start,2),
            "raw_top5": [{"title": files[r.id].title, **r.metadata} for r in raw[:5]]}
        report.append(row)
        print(json.dumps({k:v for k,v in row.items() if k != "raw_top5"}), flush=True)
    with open("/tmp/semantic-evaluation.json", "w") as output:
        json.dump(report, output, indent=2)
    print("Passed", sum(r["passed"] for r in report), "of", len(report), flush=True)


if __name__ == "__main__":
    main()

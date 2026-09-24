"""Live acceptance checks for the current labelled sample catalog."""
import json
import time
import httpx
from modules.shared.integration import service_headers

CASES = {
    "dog": ["Golden Retriever Playing With Red Ball", "Responsible Dog Care Guide"],
    "canine": ["Golden Retriever Playing With Red Ball", "Responsible Dog Care Guide"],
    "man": ["Friends Playing Outdoor Basketball", "Conversation: Joy"],
    "person walking": ["Rainy City Street With Yellow Taxi"],
    "baked goods": ["Artisan Bakery Bread Counter"],
    "basketball": ["Friends Playing Outdoor Basketball"],
    "red ball": ["Golden Retriever Playing With Red Ball"],
    "winter cottage": ["Snowy Cabin In Pine Forest"],
    "train": ["Duplicate Passenger Train"],
    "pizza": ["Fresh Vegetable Pizza"],
    "car maintenance": ["Car Maintenance Schedule"],
    "phishing protection": ["Cybersecurity Risk Brief"],
    "customer complaint": ["Customer Complaint Response Guide"],
    "dog without a ball": ["Responsible Dog Care Guide"],
    "quantum cryptography": [], "zzxqvbnm": [], "!!!": [],
}


def main():
    report = []
    with httpx.Client(base_url="http://search:8000", timeout=180) as client:
        def post(path, body):
            response = client.post(path, json=body, headers=service_headers("search", ["search:read"], "search-quality-verification"))
            response.raise_for_status()
            return response.json()
        for mode in ("vector", "hybrid"):
            for query, expected in CASES.items():
                start = time.monotonic()
                data = post("/search", {"query": query, "search_mode": mode, "limit": 100})
                names = [r["title"] for r in data["results"]]
                passed = all(title in names[:5] for title in expected) if expected else not names
                if query == "dog without a ball":
                    passed = passed and "Golden Retriever Playing With Red Ball" not in names
                assert data["facets"]["total_matches"] == data["total"]
                report.append({"mode": mode, "query": query, "passed": passed, "count": len(names), "top5": names[:5], "seconds": round(time.monotonic()-start,2)})
                # Preserve completed checks if connectivity interrupts a later request.
                with open("/tmp/live-search-verification.json", "w") as output:
                    json.dump(report, output, indent=2)
                print(json.dumps(report[-1]), flush=True)
        for mode in ("text", "vector", "hybrid"):
            base = {"query": "dog", "search_mode": mode}
            data = post("/search", {**base, "limit": 100})
            ids = [r["file_id"] for r in data["results"]]
            plan = post("/search/download-plan", {**base, "count": 2, "include_ids": True})
            assert plan["file_ids"] == ids[:2], (mode, "download ordering")
            pages = []
            for offset in range(min(3, len(ids))):
                pages.extend(r["file_id"] for r in post("/search", {**base, "limit": 1, "offset": offset})["results"])
            assert pages == ids[:3], (mode, "pagination")
            for filters in ({"file_types": ["image"]}, {"min_size": 1000000}, {"max_size": 100000}, {"resolutions": ["unknown"]}):
                filtered = post("/search", {**base, "limit": 100, "filters": filters})
                assert filtered["facets"]["total_matches"] == filtered["total"]
                for row in filtered["results"]:
                    if "file_types" in filters: assert row["file_type"] == "image"
                    if "min_size" in filters: assert row["file_size"] >= filters["min_size"]
                    if "max_size" in filters: assert row["file_size"] <= filters["max_size"]
            print(mode, "pagination/download/filter checks PASS", flush=True)
        data = post("/search", {"query": "dog-golden-retriever-red-ball.png", "limit": 100})
        assert data["results"] and all(r["file_name"] == "dog-golden-retriever-red-ball.png" for r in data["results"])
        hybrid = post("/search", {"query": "*", "search_mode": "hybrid", "limit": 100})
        keyword = post("/search", {"query": "*", "search_mode": "text", "limit": 100})
        assert [r["file_id"] for r in hybrid["results"]] == [r["file_id"] for r in keyword["results"]]
    with open("/tmp/live-search-verification.json", "w") as output:
        json.dump(report, output, indent=2)
    print("PASS", sum(r["passed"] for r in report), "/", len(report), flush=True)
    assert all(row["passed"] for row in report), "Relevance regressions found; inspect the report"


if __name__ == "__main__":
    main()

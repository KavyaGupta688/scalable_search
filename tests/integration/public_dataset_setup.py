"""Create bounded, read-only public ABO sources through the real browser API.

Run once in the gateway container. Reuses named connectors but never writes S3.
Prints only connector/run identifiers, not credentials or session tokens.
"""
import json
import os
import httpx


def main():
    with httpx.Client(base_url="http://gateway:8000", timeout=120) as client:
        def call(method, path, **kw):
            response = client.request(method, path, **kw)
            response.raise_for_status()
            return response.json() if response.content else None
        token = call("POST", "/auth/login", json={"email": os.environ["BOOTSTRAP_ADMIN_EMAIL"],
                    "password": os.environ["BOOTSTRAP_ADMIN_PASSWORD"], "role": "admin"})["access_token"]
        client.headers["Authorization"] = "Bearer " + token
        try:
            existing = call("GET", "/admin/connectors")
            if isinstance(existing, dict):
                existing = existing.get("connectors", existing.get("items", []))
            results = []
            for name, prefix, cap in [
                ("ABO real product photographs (6)", "images/original/00/", 6),
                ("ABO research paper", "static_html/ABO_CVPR2022.pdf", 1),
            ]:
                connector = next((x for x in existing if x["name"] == name), None)
                if connector is None:
                    connector = call("POST", "/admin/connectors", json={"name": name, "source_type": "S3", "s3": {
                        "endpoint_url": "https://s3.us-east-1.amazonaws.com", "bucket": "amazon-berkeley-objects",
                        "auth_mode": "anonymous", "metadata_mode": "none", "addressing_style": "virtual",
                        "prefix": prefix, "max_objects": cap, "page_size": cap}})
                cid = connector["id"]
                test = call("POST", f"/admin/connectors/{cid}/test")
                run = call("POST", f"/admin/ingestion/trigger/{cid}")
                results.append({"name": name, "connector_id": cid, "prefix": prefix, "cap": cap, "test": test, "run_id": run["run_id"]})
            print(json.dumps(results, indent=2))
        finally:
            call("POST", "/auth/logout")


if __name__ == "__main__":
    main()

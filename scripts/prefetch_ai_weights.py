"""Download large model artifacts into the shared cache without loading models.

Can run alongside provision_ai_models.py: Hugging Face uses per-file locks.
This is a provisioning tool, not a background enrichment worker.
"""
import concurrent.futures
import json
import os
from pathlib import Path
import sys
import time

os.environ.setdefault("HF_HOME", "/models/huggingface")
os.environ.setdefault("TORCH_HOME", "/models/torch")
os.environ.setdefault("XDG_CACHE_HOME", "/models/cache")
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", "/models/sentence-transformers")
os.environ["HOME"] = "/models/home"
if Path("/models/ca/ca-bundle.pem").is_file():
    os.environ.setdefault("REQUESTS_CA_BUNDLE", "/models/ca/ca-bundle.pem")
    os.environ.setdefault("SSL_CERT_FILE", "/models/ca/ca-bundle.pem")

REPOSITORIES = ["Salesforce/blip-image-captioning-base", "facebook/bart-large-mnli",
                "facebook/bart-large-cnn", "sentence-transformers/all-MiniLM-L6-v2",
                "bert-base-uncased", "roberta-base"]


def download(name):
    if name in REPOSITORIES:
        from huggingface_hub import snapshot_download
        patterns = ["*.json", "*.txt", "*.model"]
        if name not in ("bert-base-uncased", "roberta-base"):
            patterns.append("pytorch_model.bin")
        path = snapshot_download(name, allow_patterns=patterns, max_workers=2)
        return {"ready": True, "snapshot": path}
    if name == "whisper":
        import whisper
        from model_download import download
        url = whisper._MODELS["large-v3"]
        path = download(url, Path("/models/cache/whisper/large-v3.pt"), url.split("/")[-2])
        return {"ready": True, "path": path}
    if name == "toxicity":
        import torch
        from detoxify.detoxify import MODEL_URLS
        from urllib.parse import urlparse
        url = MODEL_URLS["unbiased"]
        target = Path(torch.hub.get_dir()) / "checkpoints" / Path(urlparse(url).path).name
        target.parent.mkdir(parents=True, exist_ok=True)
        from model_download import download
        # The release filename contains its expected SHA256 prefix.
        checksum = target.stem.rsplit("-", 1)[-1]
        download(url, target, checksum)
        return {"ready": True, "path": str(target)}


def main():
    output = Path("/models/provisioning")
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        names = REPOSITORIES if "--repositories-only" in sys.argv else ["whisper", "toxicity"] if "--audio-only" in sys.argv else REPOSITORIES + ["whisper", "toxicity"]
        jobs = {pool.submit(download, name): name for name in names}
        for job in concurrent.futures.as_completed(jobs):
            name = jobs[job]
            try:
                results[name] = job.result()
            except Exception as exc:
                results[name] = {"ready":False, "error":str(exc)}
            (output / "prefetch-results.json").write_text(json.dumps(results, indent=2))
            print(name, json.dumps(results[name]), flush=True)
    sys.exit(0 if all(r["ready"] for r in results.values()) else 1)


if __name__ == "__main__":
    main()

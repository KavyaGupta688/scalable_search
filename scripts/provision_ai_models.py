"""Provision and exercise the configured AI models without touching a database.

Run inside the AI image with the persistent /models volume mounted. Each model
gets a fresh process so large CPU models do not accumulate in memory. Results
and logs stay in model storage, never in Git. A failed model does not prevent
the other models from being checked; the command exits nonzero on any failure.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import zipfile

MODELS = ["clip", "yolo", "blip", "whisper", "ram", "paddleocr", "presidio",
          "nudenet", "bart_mnli", "spacy", "keybert", "summarizer",
          "face_detector", "toxicity", "ai_generated_detector"]
RAM_SHA256 = "497c178836ba66698ca226c7895317e6e800034be986452dbd2593298d50e87d"


def ram_checkpoint(root):
    from huggingface_hub import hf_hub_download

    target = Path(os.environ.get("RAM_CHECKPOINT_PATH", str(root / "ram_plus_swin_large_14m.pth")))
    if not target.is_file():
        downloaded = Path(hf_hub_download(
            "xinyu1205/recognize-anything-plus-model", "ram_plus_swin_large_14m.pth",
            revision="main", local_dir=str(target.parent),
        ))
        if downloaded != target:
            raise RuntimeError("Checkpoint destination differs from runtime configuration")
    with target.open("rb") as checkpoint:
        digest = hashlib.file_digest(checkpoint, "sha256").hexdigest()
    if digest != RAM_SHA256:
        raise RuntimeError("RAM++ checkpoint SHA256 does not match the official release")
    print("RAM++ checkpoint SHA256 verified", flush=True)


def load_one(name, root):
    # Keep auxiliary libraries' caches in shared persistent storage too.
    os.environ.setdefault("HF_HOME", str(root / "huggingface"))
    os.environ.setdefault("TORCH_HOME", str(root / "torch"))
    os.environ.setdefault("XDG_CACHE_HOME", str(root / "cache"))
    os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(root / "sentence-transformers"))
    os.environ.setdefault("YOLO_CONFIG_DIR", str(root / "ultralytics"))
    os.environ.setdefault("YOLO_MODEL_NAME", str(root / "yolov8s.pt"))
    os.environ["HOME"] = str(root / "home")
    bundle = root / "ca/ca-bundle.pem"
    if bundle.is_file():
        os.environ.setdefault("REQUESTS_CA_BUNDLE", str(bundle))
        os.environ.setdefault("SSL_CERT_FILE", str(bundle))
    Path(os.environ["HOME"]).mkdir(parents=True, exist_ok=True)
    # Limit thread pools on the local CPU to avoid oversubscription.
    os.environ.setdefault("OMP_NUM_THREADS", "2")
    os.environ.setdefault("MKL_NUM_THREADS", "2")
    if name == "ram":
        ram_checkpoint(root)
    if name == "presidio":
        # Store the model itself on the volume, not just in one container's
        # site-packages. APIs, consumers and workers must share the same model.
        from filelock import FileLock
        target = root / "spacy/en_core_web_lg"
        os.environ.setdefault("PRESIDIO_MODEL_PATH", str(target))
        wheels = root / "wheels"
        wheels.mkdir(parents=True, exist_ok=True)
        wheel = wheels / "en_core_web_lg-3.7.1-py3-none-any.whl"
        with FileLock(str(wheel) + ".lock"):
            if not (target / ".provisioned").is_file():
                if not wheel.is_file():
                    temporary = wheel.with_suffix(".partial")
                    urllib.request.urlretrieve(
                        "https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.7.1/" + wheel.name,
                        temporary,
                    )
                    temporary.replace(wheel)
                prefix = "en_core_web_lg/en_core_web_lg-3.7.1/"
                with zipfile.ZipFile(wheel) as archive:
                    for member in archive.infolist():
                        if not member.filename.startswith(prefix) or member.is_dir():
                            continue
                        relative = Path(member.filename[len(prefix):])
                        if relative.is_absolute() or ".." in relative.parts:
                            raise ValueError("Unsafe model archive path")
                        destination = target / relative
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(archive.read(member))
                (target / ".provisioned").write_text("en_core_web_lg-3.7.1")
    from modules.ai_tag_description_generation.worker.pipeline.model_manager import get_model
    model = get_model(name)
    if name == "face_detector":
        # The wrapper is lazy: construct the underlying model to fetch weights.
        from retinaface import RetinaFace
        RetinaFace.build_model()
    print(f"READY: {name} ({type(model).__name__})", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", choices=MODELS, default=MODELS)
    parser.add_argument("--one", choices=MODELS)
    parser.add_argument("--root", default="/models")
    parser.add_argument("--report", default="results.json")
    args = parser.parse_args()
    root = Path(args.root)
    if args.one:
        load_one(args.one, root)
        return
    output = root / "provisioning"
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for name in args.models:
        started = time.time()
        print(f"Provisioning {name}", flush=True)
        with (output / f"{name}.log").open("w") as log:
            result = subprocess.run([sys.executable, "-u", __file__, "--one", name,
                                     "--root", str(root)], stdout=log, stderr=subprocess.STDOUT)
        results[name] = {"ready": result.returncode == 0, "exit_code": result.returncode,
                         "seconds": round(time.time() - started, 1)}
        report = output / Path(args.report).name
        temporary = report.with_suffix(".tmp")
        temporary.write_text(json.dumps(results, indent=2))
        temporary.replace(report)
        print(name, json.dumps(results[name]), flush=True)
    sys.exit(0 if all(item["ready"] for item in results.values()) else 1)


if __name__ == "__main__":
    main()

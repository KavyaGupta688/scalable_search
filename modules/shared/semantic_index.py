"""Versioned, independent text and visual representations for retrieval."""
import os
import hashlib
import json
from functools import lru_cache
from pathlib import Path

TEXT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TEXT_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
VERSION = "multimodal-v2.1"


def collection_name():
    from modules.shared.vector_store import collection
    return os.getenv("SEMANTIC_COLLECTION", collection() + "_v2")


@lru_cache(maxsize=1)
def text_bundle():
    from transformers import AutoTokenizer, AutoModel
    return (AutoTokenizer.from_pretrained(TEXT_MODEL, revision=TEXT_REVISION),
            AutoModel.from_pretrained(TEXT_MODEL, revision=TEXT_REVISION, use_safetensors=True).eval())


def encode_passages(texts):
    import torch
    tokenizer, model = text_bundle()
    vectors = []
    for start in range(0, len(texts), 16):
        batch = tokenizer(texts[start:start+16], padding=True, truncation=True, max_length=256, return_tensors="pt")
        with torch.inference_mode():
            tokens = model(**batch).last_hidden_state
            mask = batch["attention_mask"].unsqueeze(-1)
            pooled = (tokens * mask).sum(1) / mask.sum(1).clamp_min(1)
            vectors.extend(torch.nn.functional.normalize(pooled, dim=1).cpu().tolist())
    return vectors


def text_passages(metadata):
    # Tags are retained as payload, not allowed to dominate the content vector.
    fields = ("title", "short_description", "description", "long_description", "caption",
              "native_document_text", "ocr_text", "transcribed_text", "transcript")
    passages = []
    tokenizer, _ = text_bundle()
    for field in fields:
        value = str(metadata.get(field) or "").strip()
        if not value:
            continue
        ids = tokenizer.encode(value, add_special_tokens=False)
        for start in range(0, len(ids), 180):
            passages.append(tokenizer.decode(ids[start:start+220], skip_special_tokens=True))
    # Evenly retain coverage of long files instead of keeping just their beginning.
    passages = list(dict.fromkeys(passages))
    if len(passages) > 64:
        passages = [passages[round(i * (len(passages)-1) / 63)] for i in range(64)]
    return passages or [str(metadata.get("file_name") or "Untitled file")]


def visual_vectors(path, mime_type):
    """Original image or eight evenly spaced video frames, with source timestamps."""
    import subprocess
    import tempfile
    from PIL import Image, ImageOps
    import torch
    from modules.shared.embeddings import clip_bundle
    if not (mime_type.startswith("image/") or mime_type.startswith("video/")):
        return [], []
    bundle = clip_bundle()
    images, timestamps = [], []
    try:
        if mime_type.startswith("image/"):
            with Image.open(path) as source:
                images.append(ImageOps.exif_transpose(source).convert("RGB"))
            timestamps = [0.0]
        else:
            probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)], capture_output=True, check=True, timeout=30)
            duration = float(json.loads(probe.stdout)["format"]["duration"])
            with tempfile.TemporaryDirectory(prefix="search-frames-") as directory:
                for index in range(8):
                    timestamp = max(0.0, duration * (index + .5) / 8)
                    output = str(Path(directory) / (str(index) + ".png"))
                    subprocess.run(["ffmpeg", "-v", "error", "-ss", str(timestamp), "-i", str(path), "-frames:v", "1", "-vf", "scale=640:640:force_original_aspect_ratio=decrease", "-y", output], capture_output=True, check=True, timeout=60)
                    if Path(output).exists():
                        with Image.open(output) as source:
                            images.append(source.convert("RGB"))
                        timestamps.append(timestamp)
        result = []
        for start in range(0, len(images), 4):
            pixels = torch.stack([bundle["preprocess"](im) for im in images[start:start+4]]).to(bundle["device"])
            with torch.inference_mode():
                vectors = bundle["model"].encode_image(pixels)
                result.extend(torch.nn.functional.normalize(vectors, dim=-1).cpu().tolist())
        return result, timestamps
    finally:
        for image in images:
            image.close()


def provision(create=True):
    from qdrant_client import models
    from modules.shared.vector_store import client, resolve, layout_config, ensure_payload_indexes
    q = client()
    physical = resolve(q, collection_name())
    if physical is None:
        if not create:
            raise RuntimeError("Semantic index is not provisioned; run scripts/rebuild_semantic_index.py")
        q.create_collection(collection_name(), vectors_config={
            name: models.VectorParams(size=size, distance=models.Distance.COSINE,
                multivector_config=models.MultiVectorConfig(comparator=models.MultiVectorComparator.MAX_SIM))
            for name, size in (("text", 384), ("visual", 512))
        }, **layout_config())
        physical = collection_name()
    vectors = q.get_collection(physical).config.params.vectors
    for name, size in (("text", 384), ("visual", 512)):
        config = vectors[name]
        if config.size != size or str(config.distance).lower() != "cosine" or config.multivector_config is None:
            raise RuntimeError("Incompatible semantic index schema")
    if create:
        # Search filters this collection with the same payload keys as the CLIP collection.
        ensure_payload_indexes(q, physical, payload_indexes())
    return q


def payload_indexes():
    """CLIP-collection payload indexes plus the representation version filter."""
    from qdrant_client import models
    from modules.shared.vector_store import PAYLOAD_INDEXES
    return {**PAYLOAD_INDEXES, "representation_version": models.PayloadSchemaType.KEYWORD}


def index_file(file_id, metadata, payload, source_path=None, mime_type="", visual_error=None):
    from qdrant_client import models
    from modules.shared.vector_store import client
    passages = text_passages(metadata)
    vectors = {"text": encode_passages(passages)}
    timestamps = []
    if source_path and mime_type.startswith(("image/", "video/")):
        visual, timestamps = visual_vectors(source_path, mime_type)
        if visual:
            vectors["visual"] = visual
    payload = {**payload, "file_id": str(file_id), "representation_version": VERSION,
               "text_model": TEXT_MODEL + "@" + TEXT_REVISION, "visual_model": "ViT-B-32/openai/quickgelu",
               "passages": passages, "frame_timestamps": timestamps,
               "visual_status": "indexed" if "visual" in vectors else ("unavailable" if mime_type.startswith(("image/", "video/")) else "not_applicable"),
               "visual_error": visual_error,
               "content_hash": hashlib.sha256(json.dumps(passages, ensure_ascii=False).encode()).hexdigest()}
    client().upsert(collection_name(), points=[models.PointStruct(id=str(file_id), vector=vectors, payload=payload)], wait=True)
    return payload["visual_status"]

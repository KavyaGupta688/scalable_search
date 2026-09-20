# worker/pipeline/model_manager.py
"""
Layer 4 - Model Manager.

Loads and caches every model, plus precomputes CLIP text embeddings for
the fine-grained label sets ONCE at load time - not per image.
"""

import os
from contextlib import contextmanager

# Transformers 4.28 predates modern Keras layouts. This pipeline uses the
# PyTorch implementations exclusively, so prevent optional TensorFlow model
# imports from breaking BART/BLIP initialization on Windows.
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")

import torch
import logging
from pathlib import Path

from modules.ai_tag_description_generation.app.config import settings

MODEL_VERSIONS = {
    "clip": "ViT-B-32-openai-quickgelu",
    "yolo": Path(settings.YOLO_MODEL_NAME).stem,
    "blip": "blip-image-captioning-base",
    "whisper": "whisper-large-v3",
    "ram": "ram-plus-swin-l-14m",
    "paddleocr": "paddleocr-v4",
    "presidio": "presidio-analyzer-2.2",
    "nudenet": "nudenet-v3",
    "bart_mnli": "bart-large-mnli",
    "spacy": "en_core_web_sm",
    "keybert": "keybert-base",
    "summarizer": "bart-large-cnn",
    "face_detector": "retinaface-resnet50",
    "toxicity": "detoxify-unbiased",
    "ai_generated_detector": "clip-zero-shot",
}


def get_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


DEVICE = get_device()

_model_cache: dict = {}


def release_models():
    """Release cache ownership on memory-constrained, sequential workers."""
    import gc
    from modules.shared.embeddings import clip_bundle
    _model_cache.clear()
    _text_embedding_cache.clear()
    clip_bundle.cache_clear()
    gc.collect()
    # glibc can retain freed tensor arenas in an idle process. Return those
    # pages before another process acquires the shared inference slot.
    import ctypes
    try:
        trim = ctypes.CDLL(None).malloc_trim
    except (AttributeError, OSError):
        return  # Not every platform uses glibc.
    trim.argtypes = [ctypes.c_size_t]
    trim.restype = ctypes.c_int
    trim(0)


@contextmanager
def model_execution_slot():
    """Serialize local consumer/Celery inference when they share limited RAM."""
    from contextlib import nullcontext
    from filelock import FileLock
    path = os.environ.get("AI_MODEL_EXECUTION_LOCK")
    slot = FileLock(path, timeout=600) if path else nullcontext()
    with slot:
        try:
            yield
        finally:
            if os.environ.get("AI_MODEL_CACHE_POLICY") == "single":
                release_models()


def get_model_version_string() -> str:
    return "; ".join([f"{k}={v}" for k, v in MODEL_VERSIONS.items()])


def get_model(name: str):
    """Valid names: "clip", "yolo", "blip", "whisper", "ram", "paddleocr", "presidio", "nudenet", "bart_mnli", "spacy", "keybert", "summarizer", "face_detector", "toxicity", "ai_generated_detector" """
    if name in _model_cache:
        return _model_cache[name]

    if os.environ.get("AI_MODEL_CACHE_POLICY") == "single":
        release_models()

    if name == "clip":
        model = _load_clip()
    elif name == "yolo":
        model = _load_yolo()
    elif name == "blip":
        model = _load_blip()
    elif name == "whisper":
        model = _load_whisper()
    elif name == "ram":
        model = _load_ram()
    elif name == "paddleocr":
        model = _load_paddleocr()
    elif name == "presidio":
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider

        model_path = os.environ.get("PRESIDIO_MODEL_PATH")
        if model_path:
            if not Path(model_path, "config.cfg").is_file():
                raise FileNotFoundError("Provision the Presidio spaCy model at " + model_path)
            engine = NlpEngineProvider(nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": model_path}],
            }).create_engine()
            model = AnalyzerEngine(nlp_engine=engine, supported_languages=["en"])
        else:
            model = AnalyzerEngine()
    elif name == "nudenet":
        from nudenet import NudeDetector

        model = NudeDetector()
    elif name == "bart_mnli":
        from transformers import pipeline

        model = pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
            device=0 if DEVICE == "cuda" else -1,
        )
    elif name == "spacy":
        import spacy

        model = spacy.load("en_core_web_sm")
    elif name == "keybert":
        from keybert import KeyBERT

        model = KeyBERT()
    elif name == "summarizer":
        from transformers import pipeline

        model = pipeline(
            "summarization",
            model="facebook/bart-large-cnn",
            device=0 if DEVICE == "cuda" else -1,
        )
    elif name == "face_detector":
        from retinaface import RetinaFace

        class FaceDetectorWrapper:
            def detect_faces(self, image):
                return RetinaFace.detect_faces(image)

        model = FaceDetectorWrapper()
    elif name == "toxicity":
        from detoxify import Detoxify
        from detoxify.detoxify import MODEL_URLS
        from filelock import FileLock
        from urllib.parse import urlparse

        checkpoint = Path(torch.hub.get_dir()) / "checkpoints" / Path(urlparse(MODEL_URLS["unbiased"]).path).name
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(checkpoint) + ".lock"):
            model = Detoxify("unbiased", device=DEVICE)
    elif name == "ai_generated_detector":
        model = _build_ai_generated_detector()
    else:
        raise ValueError(f"Unknown model name: {name}")

    _model_cache[name] = model
    return model


def _load_clip():
    from modules.shared.embeddings import clip_bundle

    return clip_bundle()


def _load_yolo():
    from ultralytics import YOLO

    return YOLO(settings.YOLO_MODEL_NAME)


def _load_blip():
    from transformers import BlipProcessor, BlipForConditionalGeneration

    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = (
        BlipForConditionalGeneration.from_pretrained(
            "Salesforce/blip-image-captioning-base"
        )
        .to(DEVICE)
        .eval()
    )
    return {"model": model, "processor": processor}


def _load_whisper():
    import whisper
    from filelock import FileLock
    cache = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "whisper"
    cache.mkdir(parents=True, exist_ok=True)
    # Share the prefetch lock so a worker cannot overwrite an active download.
    with FileLock(str(cache / "large-v3.pt") + ".lock"):
        if DEVICE == "cpu":
            import hashlib
            from modules.ai_tag_description_generation.worker.pipeline.whisper_loader import load_cpu_checkpoint
            path = cache / "large-v3.pt"
            if not path.is_file():
                raise FileNotFoundError("Provision Whisper large-v3 before starting the worker")
            with path.open("rb") as checkpoint:
                digest = hashlib.file_digest(checkpoint, "sha256").hexdigest()
            if digest != whisper._MODELS["large-v3"].split("/")[-2]:
                raise ValueError("Whisper large-v3 checkpoint checksum mismatch")
            return load_cpu_checkpoint(path, whisper._ALIGNMENT_HEADS["large-v3"])
        return whisper.load_model("large-v3", device=DEVICE, download_root=str(cache))


def _load_paddleocr():
    from paddleocr import PaddleOCR

    # PaddleOCR v3 removed the v2-only ``show_log`` option. Disable oneDNN:
    # some Windows PaddlePaddle builds fail when converting OCR model attributes
    # through the oneDNN/PIR runtime.
    # Explicitly retain the v4 checkpoint family recorded in MODEL_VERSIONS.
    # PaddleOCR v3 otherwise selects newer checkpoints by default.
    return PaddleOCR(use_angle_cls=True, lang="en", ocr_version="PP-OCRv4", enable_mkldnn=False)


def _load_ram():
    # Requires: git clone + pip install -e . from
    # https://github.com/xinyu1205/recognize-anything, plus the
    # ram_plus_swin_large_14m.pth checkpoint downloaded manually - see
    # setup notes. Not a standard PyPI package, so this import will fail
    # with a clear ModuleNotFoundError until that's done.
    if not Path(settings.RAM_CHECKPOINT_PATH).is_file():
        raise FileNotFoundError(
            "Required RAM++ checkpoint is not installed: "
            + settings.RAM_CHECKPOINT_PATH
        )
    from ram.models import ram_plus
    from ram import get_transform

    image_size = 384
    model = ram_plus(
        pretrained=settings.RAM_CHECKPOINT_PATH,
        image_size=image_size,
        vit="swin_l",
    )
    model = model.eval().to(DEVICE)
    transform = get_transform(image_size=image_size)
    return {"model": model, "transform": transform}


def _build_ai_generated_detector():
    """
    CLIP zero-shot AI-generated image detector.

    Compares image embeddings against text prompts for "AI generated" vs
    "real photograph" and returns a score (0.0 = real, 1.0 = AI generated).
    """
    clip_bundle = get_model("clip")
    clip_model = clip_bundle["model"]
    tokenizer = clip_bundle["tokenizer"]
    preprocess = clip_bundle["preprocess"]

    ai_prompts = [
        "an AI generated image",
        "a synthetic image made by artificial intelligence",
        "a computer generated image",
        "a deepfake image",
    ]
    real_prompts = [
        "a real photograph",
        "a photo taken by a camera",
        "a natural photograph of a real scene",
        "an authentic unedited photograph",
    ]

    with torch.no_grad():
        ai_tokens = tokenizer(ai_prompts).to(DEVICE)
        real_tokens = tokenizer(real_prompts).to(DEVICE)
        ai_text_features = clip_model.encode_text(ai_tokens)
        real_text_features = clip_model.encode_text(real_tokens)
        ai_text_features /= ai_text_features.norm(dim=-1, keepdim=True)
        real_text_features /= real_text_features.norm(dim=-1, keepdim=True)
        # Average the prompt embeddings for a more robust centroid
        ai_centroid = ai_text_features.mean(dim=0, keepdim=True)
        ai_centroid /= ai_centroid.norm(dim=-1, keepdim=True)
        real_centroid = real_text_features.mean(dim=0, keepdim=True)
        real_centroid /= real_centroid.norm(dim=-1, keepdim=True)

    class AIGeneratedDetector:
        def __init__(self):
            self.clip_model = clip_model
            self.preprocess = preprocess
            self.ai_centroid = ai_centroid
            self.real_centroid = real_centroid

        def score(self, image) -> float:
            """Return 0.0–1.0 score where higher = more likely AI-generated."""
            image_input = self.preprocess(image).unsqueeze(0).to(DEVICE)
            with torch.no_grad():
                image_features = self.clip_model.encode_image(image_input)
                image_features /= image_features.norm(dim=-1, keepdim=True)
                ai_sim = (image_features @ self.ai_centroid.T).item()
                real_sim = (image_features @ self.real_centroid.T).item()
            # Softmax over the two similarities to get a probability
            import math

            exp_ai = math.exp(ai_sim * 100.0)
            exp_real = math.exp(real_sim * 100.0)
            return exp_ai / (exp_ai + exp_real)

    return AIGeneratedDetector()


# --- Precomputed CLIP text embeddings - used only by the fine-grained
# conditional classification pass in tagging.py, not the main tagging pass
# (RAM now owns open-vocabulary tagging). ---
_text_embedding_cache: dict[tuple[str, tuple[str, ...]], torch.Tensor] = {}


def encode_text(labels: list[str]) -> torch.Tensor:
    from modules.shared.embeddings import encode_text as shared_encode

    return shared_encode(labels)


def get_text_embeddings(label_set_name: str, labels: list):
    cache_key = (label_set_name, tuple(labels))
    if cache_key in _text_embedding_cache:
        return _text_embedding_cache[cache_key]

    text_features = encode_text(labels)
    _text_embedding_cache[cache_key] = text_features
    return text_features

# worker/pipeline/model_manager.py
"""
Layer 4 - Model Manager.

Loads and caches every model, plus precomputes CLIP text embeddings for
the fine-grained label sets ONCE at load time - not per image.
"""

import torch
import logging

from app.config import settings

MODEL_VERSIONS = {
    'clip': 'ViT-B-32-openai',
    'yolo': 'yolov8n',
    'blip': 'blip-image-captioning-base',
    'whisper': 'whisper-large-v3',
    'ram': 'ram-plus-swin-l-14m',
    'paddleocr': 'paddleocr-v4',
    'presidio': 'presidio-analyzer-2.2',
    'nudenet': 'nudenet-v3',
    'bart_mnli': 'bart-large-mnli',
    'spacy': 'en_core_web_sm',
    'keybert': 'keybert-base',
    'summarizer': 'bart-large-cnn',
    'face_detector': 'retinaface-resnet50',
    'toxicity': 'detoxify-unbiased',
    'ai_generated_detector': 'clip-zero-shot',
}


def get_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


DEVICE = get_device()

_model_cache: dict = {}


def get_model_version_string() -> str:
    return "; ".join([f"{k}={v}" for k, v in MODEL_VERSIONS.items()])


def get_model(name: str):
    """Valid names: "clip", "yolo", "blip", "whisper", "ram", "paddleocr", "presidio", "nudenet", "bart_mnli", "spacy", "keybert", "summarizer", "face_detector", "toxicity", "ai_generated_detector" """
    if name in _model_cache:
        return _model_cache[name]

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
        model = AnalyzerEngine()
    elif name == "nudenet":
        from nudenet import NudeDetector
        model = NudeDetector()
    elif name == "bart_mnli":
        from transformers import pipeline
        model = pipeline("zero-shot-classification", model="facebook/bart-large-mnli", device=0 if DEVICE=="cuda" else -1)
    elif name == "spacy":
        import spacy
        model = spacy.load("en_core_web_sm")
    elif name == "keybert":
        from keybert import KeyBERT
        model = KeyBERT()
    elif name == "summarizer":
        from transformers import pipeline
        model = pipeline("summarization", model="facebook/bart-large-cnn", device=0 if DEVICE=="cuda" else -1)
    elif name == "face_detector":
        from retinaface import RetinaFace
        class FaceDetectorWrapper:
            def detect_faces(self, image):
                return RetinaFace.detect_faces(image)
        model = FaceDetectorWrapper()
    elif name == "toxicity":
        from detoxify import Detoxify
        model = Detoxify('unbiased', device=DEVICE)
    elif name == "ai_generated_detector":
        model = _build_ai_generated_detector()
    else:
        raise ValueError(f"Unknown model name: {name}")

    _model_cache[name] = model
    return model


def _load_clip():
    import open_clip

    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="openai"
    )
    model = model.to(DEVICE).eval()
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    return {"model": model, "preprocess": preprocess, "tokenizer": tokenizer}


def _load_yolo():
    from ultralytics import YOLO

    return YOLO("yolov8n.pt")


def _load_blip():
    from transformers import BlipProcessor, BlipForConditionalGeneration

    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained(
        "Salesforce/blip-image-captioning-base"
    ).to(DEVICE).eval()
    return {"model": model, "processor": processor}


def _load_whisper():
    import whisper

    return whisper.load_model("large-v3", device=DEVICE)

def _load_paddleocr():
    from paddleocr import PaddleOCR

    return PaddleOCR(use_angle_cls=True, lang="en", show_log=False)


def _load_ram():
    # Requires: git clone + pip install -e . from
    # https://github.com/xinyu1205/recognize-anything, plus the
    # ram_plus_swin_large_14m.pth checkpoint downloaded manually - see
    # setup notes. Not a standard PyPI package, so this import will fail
    # with a clear ModuleNotFoundError until that's done.
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
_text_embedding_cache: dict = {}


def get_text_embeddings(label_set_name: str, labels: list):
    if label_set_name in _text_embedding_cache:
        return _text_embedding_cache[label_set_name]

    clip_bundle = get_model("clip")
    model, tokenizer = clip_bundle["model"], clip_bundle["tokenizer"]
    text_inputs = tokenizer(labels).to(DEVICE)
    with torch.no_grad():
        text_features = model.encode_text(text_inputs)
        text_features /= text_features.norm(dim=-1, keepdim=True)

    _text_embedding_cache[label_set_name] = text_features
    return text_features
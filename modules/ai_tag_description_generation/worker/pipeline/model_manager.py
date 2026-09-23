# worker/pipeline/model_manager.py
"""
Layer 4 - Model Manager.

Loads and caches every model, plus precomputes CLIP text embeddings for
the fine-grained label sets ONCE at load time - not per image.
"""

import os

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
    'clip': 'ViT-B-32-openai',
    'yolo': Path(settings.YOLO_MODEL_NAME).stem,
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
    'ai_generated_detector': settings.AI_GENERATED_MODEL_NAME,
}


def get_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


DEVICE = get_device()

_model_cache: dict = {}


class AIGeneratedDetector:
    """Adapt a one-logit image classifier to the pipeline's score contract."""

    def __init__(self, model, preprocess, device: str = DEVICE):
        self.model = model
        self.preprocess = preprocess
        self.device = device

    def score(self, image) -> float:
        """Return the checkpoint's probability that the image is generated."""
        image_input = self.preprocess(image.convert("RGB")).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            logit = self.model(image_input).reshape(-1)[0]
            probability = torch.sigmoid(logit)
        return float(probability.cpu().item())


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

    return YOLO(settings.YOLO_MODEL_NAME)


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

    # PaddleOCR v3 removed the v2-only ``show_log`` option. Disable oneDNN:
    # some Windows PaddlePaddle builds fail when converting OCR model attributes
    # through the oneDNN/PIR runtime.
    return PaddleOCR(use_angle_cls=True, lang="en", enable_mkldnn=False)


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
    Load the Community Forensics binary classifier from Hugging Face.

    The checkpoint emits one logit where label 0 is real and label 1 is
    AI-generated. Its official evaluation transform resizes the shorter image
    edge to 440 pixels, takes a 384-pixel center crop, and applies ImageNet
    normalization.
    """
    import torch.nn as nn
    import timm
    from huggingface_hub import PyTorchModelHubMixin
    from torchvision import transforms

    class CommunityForensicsClassifier(nn.Module, PyTorchModelHubMixin):
        """Architecture used by the official Community Forensics checkpoint."""

        def __init__(
            self,
            model_size: str = "small",
            input_size: int = 384,
            patch_size: int = 16,
            freeze_backbone: bool = False,
            device: str = DEVICE,
            dtype: torch.dtype = torch.float32,
        ):
            super().__init__()
            if (model_size, input_size, patch_size) != ("small", 384, 16):
                raise ValueError(
                    "OwensLab/commfor-model-384 requires model_size='small', "
                    "input_size=384, and patch_size=16"
                )

            # The Hub checkpoint contains the complete backbone. Avoid a second
            # download of timm's ImageNet initialization before loading it.
            self.vit = timm.create_model(
                "vit_small_patch16_384.augreg_in21k_ft_in1k",
                pretrained=False,
            )
            self.vit.head = nn.Linear(384, 1, bias=True)
            if freeze_backbone:
                for parameter in self.vit.parameters():
                    parameter.requires_grad = False
                for parameter in self.vit.head.parameters():
                    parameter.requires_grad = True
            self.to(device=device, dtype=dtype)

        def forward(self, image_tensor):
            return self.vit(image_tensor)

    model = CommunityForensicsClassifier.from_pretrained(
        settings.AI_GENERATED_MODEL_NAME,
        device=DEVICE,
        map_location=DEVICE,
        strict=True,
    ).eval()
    preprocess = transforms.Compose([
        transforms.Resize(440),
        transforms.CenterCrop(384),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])

    return AIGeneratedDetector(model, preprocess)


# --- Precomputed CLIP text embeddings - used only by the fine-grained
# conditional classification pass in tagging.py, not the main tagging pass
# (RAM now owns open-vocabulary tagging). ---
_text_embedding_cache: dict[tuple[str, tuple[str, ...]], torch.Tensor] = {}


def encode_text(labels: list[str]) -> torch.Tensor:
    """Encode dynamic text without retaining document-specific tensors."""
    clip_bundle = get_model("clip")
    model, tokenizer = clip_bundle["model"], clip_bundle["tokenizer"]
    text_inputs = tokenizer(labels).to(DEVICE)
    with torch.no_grad():
        text_features = model.encode_text(text_inputs)
        text_features /= text_features.norm(dim=-1, keepdim=True)
    return text_features


def get_text_embeddings(label_set_name: str, labels: list):
    cache_key = (label_set_name, tuple(labels))
    if cache_key in _text_embedding_cache:
        return _text_embedding_cache[cache_key]

    text_features = encode_text(labels)
    _text_embedding_cache[cache_key] = text_features
    return text_features

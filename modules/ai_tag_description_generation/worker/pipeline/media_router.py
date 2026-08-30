# worker/pipeline/media_router.py
"""
Layer 5 - Media Router.

Routes an incoming file to the correct processing lane based on its type.
Pure logic, no external dependencies - testable standalone.
"""

from dataclasses import dataclass
from enum import Enum


class Modality(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    CSV = "csv"
    UNKNOWN = "unknown"


@dataclass
class ModalityPolicy:
    max_keyframes: int = 20
    ocr_required: bool = False
    model_tier: str = 'standard'  # 'standard' | 'high' | 'lightweight'
    requires_audio_extraction: bool = False
    requires_vision_models: bool = True
    requires_text_models: bool = False


# Extension -> modality mapping. Extend this as you encounter new formats
# during testing - don't try to guess every possible extension upfront.
_EXTENSION_MAP = {
    "jpg": Modality.IMAGE,
    "jpeg": Modality.IMAGE,
    "png": Modality.IMAGE,
    "webp": Modality.IMAGE,
    "bmp": Modality.IMAGE,

    "mp4": Modality.VIDEO,
    "mov": Modality.VIDEO,
    "avi": Modality.VIDEO,
    "mkv": Modality.VIDEO,

    "mp3": Modality.AUDIO,
    "wav": Modality.AUDIO,
    "flac": Modality.AUDIO,
    "m4a": Modality.AUDIO,

    "pdf": Modality.DOCUMENT,
    "docx": Modality.DOCUMENT,
    "doc": Modality.DOCUMENT,
    "txt": Modality.DOCUMENT,

    "csv": Modality.CSV,
    "tsv": Modality.CSV,
}


def get_modality_policy(modality: Modality) -> ModalityPolicy:
    if modality == Modality.IMAGE:
        return ModalityPolicy(ocr_required=True, requires_vision_models=True)
    elif modality == Modality.VIDEO:
        return ModalityPolicy(max_keyframes=20, ocr_required=True, requires_audio_extraction=True, requires_vision_models=True)
    elif modality == Modality.AUDIO:
        return ModalityPolicy(requires_vision_models=False, requires_text_models=True, requires_audio_extraction=True)
    elif modality == Modality.DOCUMENT:
        return ModalityPolicy(ocr_required=True, requires_vision_models=False, requires_text_models=True)
    elif modality == Modality.CSV:
        return ModalityPolicy(requires_vision_models=False, requires_text_models=True)
    
    return ModalityPolicy()


def route_file(file_path: str, file_type: str | None = None) -> tuple[Modality, ModalityPolicy]:
    """
    Determine which processing lane a file belongs to.

    file_type, if provided, is trusted over guessing from the path (e.g.
    Module 1 may pass the true type separately from a storage_path that
    doesn't have a clean extension, like an S3 key with no suffix).
    """
    extension = (file_type or _extension_from_path(file_path)).lower().lstrip(".")
    modality = _EXTENSION_MAP.get(extension, Modality.UNKNOWN)
    policy = get_modality_policy(modality)
    return modality, policy


def _extension_from_path(file_path: str) -> str:
    if "." not in file_path:
        return ""
    return file_path.rsplit(".", 1)[-1]


if __name__ == "__main__":
    # Quick standalone sanity check - run directly:
    #   python worker/pipeline/media_router.py
    test_cases = [
        "sample.jpg", "video.mp4", "audio.wav",
        "report.pdf", "data.csv", "unknown.xyz",
    ]
    for path in test_cases:
        modality, policy = route_file(path)
        print(f"{path:20s} -> {modality.value}, policy: {policy}")
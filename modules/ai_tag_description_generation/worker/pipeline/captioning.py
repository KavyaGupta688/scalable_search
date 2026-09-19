# worker/pipeline/captioning.py
"""
Layer 4 - Caption Generation.

BLIP-base generates short and long natural-language descriptions.
Grounded using tags already produced by tagging.py - BLIP's conditional
generation mode accepts a text prompt prefix, which we use to steer it
toward the specific things RAM/YOLO already found instead of generating
a caption blind to that context.
"""

from dataclasses import dataclass
import re
from typing import Iterable

import torch
from PIL import Image

from modules.ai_tag_description_generation.worker.pipeline.model_manager import get_model, DEVICE
from modules.ai_tag_description_generation.worker.pipeline.tagging import Tag
from modules.ai_tag_description_generation.worker.pipeline.retry_handler import DataQualityError, TransientError


SHORT_CAPTION_MAX_NEW_TOKENS = 20
LONG_CAPTION_MAX_NEW_TOKENS = 60

# How many top tags to fold into the grounding prompt - too many and the
# prompt gets noisy/contradictory, too few and grounding barely helps.
MAX_GROUNDING_TAGS = 3
MAX_VIDEO_CAPTION_FRAMES = 4
NON_SUBJECT_TAGS = {
    "black", "white", "brown", "red", "blue", "green", "yellow", "gray", "grey",
    "small", "large", "close-up", "cartoon", "illustration", "image", "photo", "picture",
}
VIDEO_STYLE_TERMS = {"animation", "animated", "cartoon", "drawing", "illustration", "sketch", "painting", "cgi"}
CONFLICTING_SUBJECTS = (
    {"dog", "cat"}, {"man", "woman"}, {"car", "truck", "bus", "motorcycle"},
)


@dataclass
class Caption:
    short_description: str
    long_description: str
    search_description: str           # NEW - keyword-dense for search indexing
    accessibility_description: str     # NEW - structured alt-text


def retry_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (DataQualityError, TransientError):
            raise
        except Exception as e:
            raise TransientError(f"{func.__name__} failed: {e}") from e
    return wrapper


@retry_handler
def generate_caption(image: Image.Image, tags: list[Tag], ocr_text: str = "") -> Caption:
    blip_bundle = get_model("blip")
    model, processor = blip_bundle["model"], blip_bundle["processor"]

    # Let BLIP describe the scene before using tags. Feeding raw tag lists as
    # a prefix makes the decoder copy awkward fragments such as "brown, chase".
    short_description = _generate(
        model, processor, image, prompt=None, max_new_tokens=SHORT_CAPTION_MAX_NEW_TOKENS
    )
    long_description = _generate(
        model, processor, image, _build_grounding_prompt(tags), max_new_tokens=LONG_CAPTION_MAX_NEW_TOKENS
    )
    if not long_description or len(long_description) <= len(short_description):
        long_description = short_description

    # If the document has OCR/transcript text, append a short factual note
    # rather than trying to force BLIP (a vision model) to reason about
    # text content it never saw as text - keeps the long description
    # honest about what came from vision vs what came from OCR.
    if ocr_text.strip():
        long_description += f" Extracted text on the file: \"{_truncate(ocr_text, 150)}\""

    search_description = _build_search_description(short_description, tags)
    accessibility_description = _build_accessibility_description(short_description, tags, "Image")

    return Caption(
        short_description=short_description, 
        long_description=long_description,
        search_description=search_description,
        accessibility_description=accessibility_description
    )


@retry_handler
def generate_video_caption(
    keyframes: list[Image.Image],
    tags: list[Tag],
    supporting_text: str = "",
    duration_seconds: float | None = None,
) -> Caption:
    """Describe a video from several representative frames.

    BLIP is an image model, so prompting one thumbnail cannot describe motion.
    We caption a small chronological frame set independently, select the most
    tag-consistent observation, and add only actions confirmed by video tags.
    """
    if not keyframes:
        return generate_text_description(supporting_text, tags, "video")

    blip_bundle = get_model("blip")
    model, processor = blip_bundle["model"], blip_bundle["processor"]
    representative_frames = _select_video_caption_frames(keyframes, MAX_VIDEO_CAPTION_FRAMES)
    observations = [
        _generate(model, processor, frame, prompt=None, max_new_tokens=30)
        for frame in representative_frames
    ]
    observations = _dedupe_phrases(observations)
    best_observation = max(observations, key=lambda value: _caption_tag_score(value, tags))

    style = next((tag.label for tag in tags if tag.category == "style"), "")
    short_description = _video_short_description(best_observation, style, tags)

    actions = list(dict.fromkeys(tag.label for tag in tags if tag.category == "action"))[:4]
    details: list[str] = [short_description]
    if actions:
        details.append(f"Across the sampled frames, detected actions include {_natural_join(actions)}.")
    if duration_seconds is not None:
        details.append(f"The video is approximately {duration_seconds:.1f} seconds long.")
    if supporting_text.strip():
        details.append(f"Extracted speech or visible text: \"{_truncate(supporting_text, 180)}\"")
    long_description = " ".join(details)

    search_description = _build_search_description(short_description, tags)
    accessibility_description = _build_accessibility_description(short_description, tags, "Video")
    return Caption(
        short_description=short_description,
        long_description=long_description,
        search_description=search_description,
        accessibility_description=accessibility_description,
    )

@retry_handler
def generate_text_description(text: str, tags: list[Tag], modality: str) -> Caption:
    if not text or not text.strip():
        return Caption(
            short_description="No text available.",
            long_description="No text available to summarize.",
            search_description=_build_search_description("No text", tags),
            accessibility_description=_build_accessibility_description("No text", tags, modality)
        )
        
    normalized_text = " ".join(text.split())
    # A generative summarizer cannot improve a short transcript and often
    # produces padding or hallucinated continuations. Preserve it instead.
    if len(normalized_text.split()) <= 60:
        long_desc = normalized_text
        short_desc = _first_sentence(normalized_text, max_chars=160)
    else:
        summarizer = get_model('summarizer')
        word_count = len(normalized_text.split())
        max_length = min(142, max(48, word_count // 2))
        summary_result = summarizer(
            normalized_text,
            max_length=max_length,
            min_length=20,
            do_sample=False,
            truncation=True,
        )
        long_desc = summary_result[0]['summary_text'].strip()
        short_desc = _first_sentence(long_desc, max_chars=160)
    
    search_desc = _build_search_description(short_desc, tags)
    acc_desc = _build_accessibility_description(short_desc, tags, modality)
    
    return Caption(
        short_description=short_desc,
        long_description=long_desc,
        search_description=search_desc,
        accessibility_description=acc_desc
    )


def generate_all_descriptions(preprocessing_result, tags: list[Tag], extracted_text_dict: dict, modality: str) -> Caption:
    text_content = extracted_text_dict.get('text', '') or extracted_text_dict.get('transcript', '') or extracted_text_dict.get('ocr', '')
    
    if modality == "image":
        image = preprocessing_result if isinstance(preprocessing_result, Image.Image) else Image.new('RGB', (100,100))
        return generate_caption(image, tags, text_content)
        
    elif modality == "video":
        frames = preprocessing_result if isinstance(preprocessing_result, list) else []
        return generate_video_caption(frames, tags, text_content)
        
    else:
        # Audio, document, csv
        return generate_text_description(text_content, tags, modality)


def _build_search_description(short_desc: str, tags: list[Tag]) -> str:
    top_tags = sorted(tags, key=lambda t: t.confidence, reverse=True)[:10]
    labels = list(dict.fromkeys(t.label for t in top_tags))
    return f"{', '.join(labels)}. {short_desc}"

def _build_accessibility_description(short_desc: str, tags: list[Tag], modality: str) -> str:
    top_tags = sorted(tags, key=lambda t: t.confidence, reverse=True)[:5]
    labels = [t.label for t in top_tags]
    tags_str = ", ".join(labels)
    modality_capitalized = modality.capitalize() if modality else "Media"
    description = short_desc.rstrip(" .")
    contents = f" Contains: {tags_str}." if tags_str else ""
    return f"[{modality_capitalized}]: {description}.{contents}"


def _build_grounding_prompt(tags: list[Tag]) -> str:
    """
    BLIP's conditional generation accepts a text prefix it continues from.
    Feeding it the top tags biases generation toward mentioning those
    specifics (e.g. "a photograph of a golden retriever" rather than
    "a photograph of a dog") without forcing exact wording.
    """
    if not tags:
        return "a photo of"

    ordered_tags = sorted(tags, key=lambda t: t.confidence, reverse=True)
    subject = next((t.label for t in ordered_tags if t.category == "fine_grained"), None)
    if not subject:
        subject = next(
            (t.label for t in ordered_tags if t.category == "object" and t.confidence >= 0.65),
            None,
        )
    if not subject:
        subject = next(
            (t.label for t in ordered_tags if t.category == "open_vocab" and t.label.lower() not in NON_SUBJECT_TAGS),
            None,
        )
    action = next((t.label for t in ordered_tags if t.category == "action"), None)
    scene = next((t.label for t in ordered_tags if t.category == "scene"), None)

    if subject:
        prompt = f"a photo of a {subject}"
        if action:
            prompt += f" {action}"
        if scene:
            prompt += f" in a {scene}"
        return prompt
    return "a photo of"


def _select_video_caption_frames(frames: list[Image.Image], limit: int) -> list[Image.Image]:
    """Choose chronological coverage including the middle/action frame."""
    if len(frames) <= limit:
        return frames
    indexes = {0, len(frames) // 2, len(frames) - 1}
    while len(indexes) < limit:
        candidates = [index for index in range(len(frames)) if index not in indexes]
        next_index = max(candidates, key=lambda index: min(abs(index - selected) for selected in indexes))
        indexes.add(next_index)
    return [frames[index] for index in sorted(indexes)[:limit]]


def _dedupe_phrases(values: Iterable[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(value.strip().split())
        key = re.sub(r"[^a-z0-9 ]", "", cleaned.casefold())
        if cleaned and key not in seen:
            unique.append(cleaned)
            seen.add(key)
    return unique or ["Video content could not be described."]


def _caption_tag_score(caption: str, tags: list[Tag]) -> float:
    words = set(re.findall(r"[a-z0-9]+", caption.casefold()))
    labels = {tag.label.casefold() for tag in tags}
    score = sum(
        tag.confidence
        for tag in tags
        if tag.category in {"object", "fine_grained", "open_vocab", "scene", "action"}
        and set(tag.label.casefold().split()) <= words
    )
    for group in CONFLICTING_SUBJECTS:
        expected = group & labels
        mentioned = group & words
        if expected and mentioned and not (mentioned & expected):
            score -= 2.0
    return score


def _video_short_description(observation: str, style: str, tags: list[Tag]) -> str:
    observation = observation.strip().rstrip(".")
    if style.casefold() in VIDEO_STYLE_TERMS:
        subjects = _video_subjects(tags)
        if subjects:
            subject_phrase = _natural_join([_with_indefinite_article(subject) for subject in subjects])
            article = "An" if style.casefold() in {"animation", "animated", "illustration"} else "A"
            return f"{article} {style.casefold()} video showing {subject_phrase}."
        # Avoid "a photo" for animation and retain the visual model's factual
        # subject/setting observation.
        observation = re.sub(r"^a (photo|photograph|picture|cartoon) of ", "", observation, flags=re.I)
        article = "An" if style.casefold() in {"animation", "animated", "illustration"} else "A"
        return f"{article} {style.casefold()} video showing {observation}."
    return f"A video showing {observation}."


def _video_subjects(tags: list[Tag]) -> list[str]:
    candidates = list(dict.fromkeys(
        tag.label.casefold()
        for tag in tags
        if tag.category in {"object", "fine_grained", "open_vocab"}
        and tag.label.casefold() not in NON_SUBJECT_TAGS
    ))
    specific_people = {"man", "woman", "boy", "girl", "child", "baby"} & set(candidates)
    if specific_people:
        candidates = [candidate for candidate in candidates if candidate not in {"person", "people"}]
    people = {"man", "woman", "boy", "girl", "child", "baby", "person", "people"}
    animals = {"dog", "cat", "bird", "horse", "cow", "sheep", "elephant", "bear"}
    candidates.sort(key=lambda value: (0 if value in people else 1 if value in animals else 2))
    return candidates[:3]


def _with_indefinite_article(value: str) -> str:
    if value in {"people", "children"} or value.endswith("s"):
        return value
    article = "an" if value[:1] in "aeiou" else "a"
    return f"{article} {value}"


def _natural_join(values: list[str]) -> str:
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def _generate(model, processor, image: Image.Image, prompt: str | None, max_new_tokens: int) -> str:
    inputs = processor(images=image, text=prompt, return_tensors="pt").to(DEVICE) if prompt else processor(
        images=image, return_tensors="pt"
    ).to(DEVICE)
    with torch.no_grad():
        output = model.generate(
            **inputs, max_new_tokens=max_new_tokens, num_beams=4,
            repetition_penalty=1.15, early_stopping=True,
        )
    caption = processor.decode(output[0], skip_special_tokens=True)
    return caption.strip()


def _truncate(text: str, max_chars: int) -> str:
    text = text.strip().replace("\n", " ")
    return text[:max_chars] + ("..." if len(text) > max_chars else "")


def _first_sentence(text: str, max_chars: int) -> str:
    sentence = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0]
    return _truncate(sentence, max_chars)


if __name__ == "__main__":
    import sys

    from modules.ai_tag_description_generation.worker.pipeline.tagging import generate_tags, Tag

    path = sys.argv[1] if len(sys.argv) > 1 else "sample.jpg"
    try:
        image = Image.open(path).convert("RGB")
    except:
        image = Image.new('RGB', (100, 100))

    tags = generate_tags([image])
    caption = generate_caption(image, tags)

    print(f"Tags used for grounding: {[t.label for t in tags[:MAX_GROUNDING_TAGS]]}")
    print(f"Short: {caption.short_description}")
    print(f"Long: {caption.long_description}")
    print(f"Search: {caption.search_description}")
    print(f"Accessibility: {caption.accessibility_description}")

    # Test text description
    print("\nTesting text description:")
    text_tags = [Tag(label="test", confidence=1.0, source="test", category="keyword")]
    text_caption = generate_text_description("This is a sample document for testing the summarizer.", text_tags, "document")
    print(f"Short: {text_caption.short_description}")
    print(f"Long: {text_caption.long_description}")
    print(f"Search: {text_caption.search_description}")
    print(f"Accessibility: {text_caption.accessibility_description}")

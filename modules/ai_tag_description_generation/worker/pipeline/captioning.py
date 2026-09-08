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

import torch
from PIL import Image

from modules.ai_tag_description_generation.worker.pipeline.model_manager import get_model, DEVICE
from modules.ai_tag_description_generation.worker.pipeline.tagging import Tag


SHORT_CAPTION_MAX_NEW_TOKENS = 20
LONG_CAPTION_MAX_NEW_TOKENS = 60

# How many top tags to fold into the grounding prompt - too many and the
# prompt gets noisy/contradictory, too few and grounding barely helps.
MAX_GROUNDING_TAGS = 3
NON_SUBJECT_TAGS = {
    "black", "white", "brown", "red", "blue", "green", "yellow", "gray", "grey",
    "small", "large", "close-up", "cartoon", "illustration", "image", "photo", "picture",
}


@dataclass
class Caption:
    short_description: str
    long_description: str
    search_description: str           # NEW - keyword-dense for search indexing
    accessibility_description: str     # NEW - structured alt-text


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

def retry_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            import logging
            logging.error(f"Error in {func.__name__}: {e}")
            return Caption(
                short_description="Description generation failed.",
                long_description="Description generation failed due to an error.",
                search_description="",
                accessibility_description="[Error]: Description generation failed."
            )
    return wrapper

@retry_handler
def generate_text_description(text: str, tags: list[Tag], modality: str) -> Caption:
    summarizer = get_model('summarizer')
    
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
        word_count = len(normalized_text.split())
        max_length = min(142, max(48, word_count // 2))
        summary_result = summarizer(normalized_text, max_length=max_length, min_length=20, do_sample=False)
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
        # Simplified video captioning: just use thumbnail or first keyframe
        image = preprocessing_result[0] if isinstance(preprocessing_result, list) and len(preprocessing_result) > 0 else Image.new('RGB', (100,100))
        return generate_caption(image, tags, text_content)
        
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
    return f"[{modality_capitalized}]: {short_desc}. Contains: {tags_str}."


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
    subject = next((t.label for t in ordered_tags if t.category in {"object", "fine_grained"}), None)
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

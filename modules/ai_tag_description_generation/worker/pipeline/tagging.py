# worker/pipeline/tagging.py
"""
Layer 4 - Tagging & Classification.

RAM++: open-vocabulary tagging - no hardcoded label list, recognizes
thousands of categories including ones never explicitly enumerated. This
is the primary tagging pass, replacing curated CLIP label lists entirely.

YOLOv8n: object detection - gives precise bounding boxes RAM doesn't
provide, used both as extra tags and to crop regions for fine-grained
classification below.

CLIP (conditional): fine-grained sub-classification (e.g. dog breed),
triggered only when RAM or YOLO surfaces a label with known sub-categories
in FINE_GRAINED_LABELS - keeps this cheap at scale since most images never
trigger it.
"""

from dataclasses import dataclass

import torch
from PIL import Image

from modules.ai_tag_description_generation.worker.pipeline.model_manager import get_model, get_text_embeddings, DEVICE
from modules.ai_tag_description_generation.worker.pipeline.retry_handler import DataQualityError, TransientError
from modules.ai_tag_description_generation.worker.pipeline.fine_grained_taxonomy import (
    DEFAULT_FINE_GRAINED_CONFIDENCE_THRESHOLD,
    DEFAULT_FINE_GRAINED_MINIMUM_MARGIN,
    FINE_GRAINED_CONFIDENCE_THRESHOLDS,
    FINE_GRAINED_LABELS,
    FINE_GRAINED_MINIMUM_MARGINS,
    FINE_GRAINED_PROMPT_TEMPLATES,
    FINE_GRAINED_TRIGGER_ALIASES,
)


# Fine-grained sub-labels, checked only when the trigger label appears in
# RAM's or YOLO's output. This table is the extensibility point for
# specificity - add entries as your dataset reveals categories worth
# specializing, without touching the open-vocabulary tagging itself.
YOLO_CONFIDENCE_THRESHOLD = 0.55
GENERIC_TAGS = {"image", "photo", "photograph", "picture", "artwork"}

SCENE_KEYWORDS = {'indoor', 'outdoor', 'beach', 'mountain', 'forest', 'city', 'street', 'park', 'office', 'kitchen', 'bedroom', 'bathroom', 'garden', 'stadium', 'restaurant', 'school', 'hospital', 'airport', 'farm', 'desert', 'lake', 'river', 'ocean', 'sky', 'sunset', 'sunrise', 'night', 'snow', 'rain'}
ACTION_KEYWORDS = {'running', 'walking', 'sitting', 'standing', 'eating', 'drinking', 'playing', 'driving', 'reading', 'writing', 'dancing', 'singing', 'cooking', 'swimming', 'jumping', 'flying', 'climbing', 'surfing', 'skiing'}
ACTION_ALIASES = {
    'run': 'running', 'walk': 'walking', 'sit': 'sitting', 'stand': 'standing',
    'eat': 'eating', 'drink': 'drinking', 'play': 'playing', 'drive': 'driving',
    'read': 'reading', 'write': 'writing', 'dance': 'dancing', 'sing': 'singing',
    'cook': 'cooking', 'swim': 'swimming', 'jump': 'jumping', 'fly': 'flying',
    'climb': 'climbing', 'surf': 'surfing', 'ski': 'skiing', 'chase': 'chasing',
    'throw': 'throwing', 'catch': 'catching', 'fetch': 'fetching',
}
STYLE_KEYWORDS = {
    'animation', 'animated', 'cartoon', 'drawing', 'illustration', 'sketch',
    'painting', 'render', 'cgi', 'computer generated',
}
ATTRIBUTE_KEYWORDS = {
    'backpack', 'bag', 'belt', 'coat', 'collar', 'dress', 'glasses', 'hat',
    'jacket', 'leash', 'shirt', 'shoe', 'suit', 'sweater', 'trench coat',
}

@dataclass
class Tag:
    label: str
    confidence: float
    source: str          # "ram" | "yolo" | "clip_fine_grained" | "keybert" | "spacy" | "bart_mnli"
    category: str         # open_vocab/object/fine_grained/country/keyword/entity/domain/scene/action/style/attribute

def retry_handler(func):
    """Convert backend failures into an explicit retryable stage failure."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (DataQualityError, TransientError):
            raise
        except Exception as e:
            raise TransientError(f"{func.__name__} failed: {e}") from e
    return wrapper


def _classify_ram_tag_category(label: str) -> str:
    label_lower = label.lower()
    if label_lower in STYLE_KEYWORDS:
        return 'style'
    if label_lower in ATTRIBUTE_KEYWORDS:
        return 'attribute'
    if label_lower in SCENE_KEYWORDS:
        return 'scene'
    elif label_lower in ACTION_KEYWORDS or label_lower in ACTION_ALIASES:
        return 'action'
    return 'open_vocab'


def _canonicalize_ram_label(label: str) -> str:
    """Normalize action lemmas so captions can use grammatical verb forms."""
    normalized = " ".join(label.lower().split())
    return ACTION_ALIASES.get(normalized, normalized)


@retry_handler
def generate_text_tags(text: str) -> list[Tag]:
    if not text or not text.strip():
        return []
    
    tags = []
    
    # Extract keywords
    keybert = get_model('keybert')
    keywords = keybert.extract_keywords(text, top_n=10)
    for kw, score in keywords:
        tags.append(Tag(label=kw, confidence=float(score), source="keybert", category="keyword"))
        
    # Extract entities
    spacy = get_model('spacy')
    doc = spacy(text)
    for ent in doc.ents:
        # Confidence is not natively available in spaCy in the same way, assume 1.0
        tags.append(Tag(label=ent.text, confidence=1.0, source="spacy", category="entity"))
        
    return tags


@retry_handler
def generate_zero_shot_categories(text: str, candidate_categories: list | None = None) -> list[Tag]:
    if not text or not text.strip():
        return []
        
    if candidate_categories is None:
        candidate_categories = ['technology', 'science', 'sports', 'entertainment', 'business', 'health', 'education', 'politics', 'travel', 'food', 'art', 'nature', 'music', 'fashion', 'automotive']
        
    bart_mnli = get_model('bart_mnli')
    result = bart_mnli(text, candidate_categories, truncation=True)
        
    tags = []
    for label, score in zip(result['labels'], result['scores']):
        if score > 0.1:
            tags.append(Tag(label=label, confidence=float(score), source="bart_mnli", category="domain"))
            
    return tags


def generate_all_tags(images: list[Image.Image] | None, text: str | None, modality_str: str) -> list[Tag]:
    all_tags = []
    
    if modality_str in ["image", "video"] and images:
        all_tags.extend(generate_tags(images, require_video_consensus=modality_str == "video"))
        if text:
            all_tags.extend(generate_text_tags(text))
            
    elif modality_str in ["audio", "document", "csv"] and text:
        all_tags.extend(generate_text_tags(text))
        all_tags.extend(generate_zero_shot_categories(text))
        
    return _merge_and_dedupe(all_tags)


def generate_tags(images: list[Image.Image], require_video_consensus: bool = False) -> list[Tag]:
    tags_by_frame: list[list[Tag]] = []
    for image in images:
        frame_tags: list[Tag] = []
        ram_tags = _ram_tags(image)
        yolo_detections = _yolo_tags(image)

        frame_tags.extend(ram_tags)
        frame_tags.extend(t for t, _ in yolo_detections)
        frame_tags.extend(_fine_grained_tags(image, ram_tags, yolo_detections))
        tags_by_frame.append(frame_tags)

    if require_video_consensus and len(tags_by_frame) > 1:
        return _aggregate_video_tags(tags_by_frame)
    return _merge_and_dedupe([tag for frame_tags in tags_by_frame for tag in frame_tags])


def _ram_tags(image: Image.Image) -> list[Tag]:
    ram_bundle = get_model("ram")
    model, transform = ram_bundle["model"], ram_bundle["transform"]

    from ram import inference_ram
    image_input = transform(image).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        english_tags, _chinese_tags = inference_ram(image_input, model)

    # RAM returns tags as a single string like "dog | grass | outdoor | park"
    labels = [t.strip() for t in english_tags.split("|") if t.strip()]

    # RAM doesn't return per-tag confidence scores in this output format -
    # all returned tags already passed its internal threshold, so they're
    # recorded as confirmed detections rather than scored guesses.
    return [
        Tag(
            label=_canonicalize_ram_label(label),
            # RAM's public inference helper does not expose calibrated
            # per-label probabilities. Treat accepted labels as strong but
            # not certain so a synthetic 1.0 does not dominate every model.
            confidence=0.75,
            source="ram",
            category=_classify_ram_tag_category(label),
        )
        for label in labels
        if label.lower() not in GENERIC_TAGS
    ]


def _yolo_tags(image: Image.Image) -> list[tuple[Tag, tuple]]:
    """Returns (Tag, bbox) pairs - bbox lets the fine-grained pass crop
    exactly the detected region."""
    model = get_model("yolo")
    results = model.predict(image, conf=YOLO_CONFIDENCE_THRESHOLD, verbose=False)

    detections = []
    for result in results:
        for box in result.boxes:
            label = result.names[int(box.cls[0])]
            confidence = float(box.conf[0])
            bbox = tuple(box.xyxy[0].cpu().tolist())
            tag = Tag(label=label, confidence=round(confidence, 4), source="yolo", category="object")
            detections.append((tag, bbox))
    return detections


def _fine_grained_tags(
    image: Image.Image,
    ram_tags: list[Tag],
    yolo_detections: list[tuple],
) -> list[Tag]:
    # Breed/species/flag softmax scores are unreliable for drawings and
    # animation. RAM's broad labels remain available for those inputs.
    if any(tag.category == "style" for tag in ram_tags):
        return []

    trigger_labels = {t.label.lower() for t in ram_tags} | {t.label.lower() for t, _ in yolo_detections}
    matched_triggers = {
        FINE_GRAINED_TRIGGER_ALIASES.get(label, label)
        for label in trigger_labels
        if FINE_GRAINED_TRIGGER_ALIASES.get(label, label) in FINE_GRAINED_LABELS
    }
    # Do not classify both a superclass and an already detected child.
    if "animal" in matched_triggers and matched_triggers & {"dog", "cat", "bird", "horse", "fish"}:
        matched_triggers.remove("animal")

    if not matched_triggers:
        return []

    fine_tags = []
    for trigger in matched_triggers:
        crop = _best_crop_for_trigger(image, trigger, yolo_detections)
        fine_tags.extend(_clip_classify_crop(crop, trigger, FINE_GRAINED_LABELS[trigger]))
    return fine_tags


def _best_crop_for_trigger(image: Image.Image, trigger: str, yolo_detections: list[tuple]) -> Image.Image:
    matching_boxes = [
        (tag, bbox)
        for tag, bbox in yolo_detections
        if FINE_GRAINED_TRIGGER_ALIASES.get(tag.label.lower(), tag.label.lower()) == trigger
    ]
    if matching_boxes:
        best_tag, bbox = max(matching_boxes, key=lambda pair: pair[0].confidence)
        return image.crop(bbox)
    return image  # RAM-only trigger (e.g. "flower") has no YOLO box - use full image


def _clip_classify_crop(crop: Image.Image, trigger: str, sub_labels: list[str]) -> list[Tag]:
    clip_bundle = get_model("clip")
    model, preprocess = clip_bundle["model"], clip_bundle["preprocess"]

    template = FINE_GRAINED_PROMPT_TEMPLATES.get(trigger, "a photo of a {label}")
    prompts = [template.format(label=label) for label in sub_labels]
    text_features = get_text_embeddings(f"fine_grained_{trigger}", prompts)

    image_input = preprocess(crop).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        image_features = model.encode_image(image_input)
        image_features /= image_features.norm(dim=-1, keepdim=True)
        similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)

    scores = similarity[0].cpu().tolist()
    ranked_indexes = sorted(range(len(scores)), key=lambda index: scores[index], reverse=True)
    best_idx = ranked_indexes[0]
    runner_up_score = scores[ranked_indexes[1]] if len(ranked_indexes) > 1 else 0.0
    threshold = FINE_GRAINED_CONFIDENCE_THRESHOLDS.get(
        trigger, DEFAULT_FINE_GRAINED_CONFIDENCE_THRESHOLD
    )
    minimum_margin = FINE_GRAINED_MINIMUM_MARGINS.get(
        trigger, DEFAULT_FINE_GRAINED_MINIMUM_MARGIN
    )
    if scores[best_idx] >= threshold and scores[best_idx] - runner_up_score >= minimum_margin:
        return [Tag(
            label=sub_labels[best_idx],
            confidence=round(scores[best_idx], 4),
            source="clip_fine_grained",
            category="country" if trigger == "flag" else "fine_grained",
        )]
    return []


def _merge_and_dedupe(tags: list[Tag]) -> list[Tag]:
    best: dict[tuple, Tag] = {}
    for tag in tags:
        key = (tag.label.lower(), tag.source)
        if key not in best or tag.confidence > best[key].confidence:
            best[key] = tag
    return sorted(best.values(), key=lambda t: t.confidence, reverse=True)


def _aggregate_video_tags(tags_by_frame: list[list[Tag]]) -> list[Tag]:
    """Keep temporally stable labels while accounting for model/domain trust."""
    frames_by_label: dict[str, set[int]] = {}
    sources_by_label: dict[str, set[str]] = {}
    all_tags: list[Tag] = []

    for frame_index, frame_tags in enumerate(tags_by_frame):
        for tag in frame_tags:
            key = tag.label.lower()
            frames_by_label.setdefault(key, set()).add(frame_index)
            sources_by_label.setdefault(key, set()).add(tag.source)
            all_tags.append(tag)

    stylized_video = any(
        tag.source == "ram" and tag.category == "style"
        for tag in all_tags
    )
    frame_count = len(tags_by_frame)
    confirmed_labels: set[str] = set()
    for label, frame_indexes in frames_by_label.items():
        sources = sources_by_label[label]
        coverage = len(frame_indexes) / frame_count
        categories = {tag.category for tag in all_tags if tag.label.lower() == label}
        if stylized_video and sources == {"ram"} and "attribute" in categories:
            # Clothing/accessory predictions from RAM are not calibrated and
            # frequently become false relations in cartoons (for example a
            # dog edge being interpreted as a leash).
            continue
        if len(sources) >= 2:
            confirmed_labels.add(label)
        elif "ram" in sources and len(frame_indexes) >= 2:
            confirmed_labels.add(label)
        elif "yolo" in sources and not stylized_video and len(frame_indexes) >= 2 and coverage >= 0.4:
            # YOLO is trained primarily on photographs. Repeated YOLO-only
            # labels in cartoons/animation are often stable false positives.
            confirmed_labels.add(label)
        elif "yolo" not in sources and len(frame_indexes) >= 2 and coverage >= 0.4:
            confirmed_labels.add(label)

    accepted = [tag for tag in all_tags if tag.label.lower() in confirmed_labels]
    return _merge_and_dedupe(accepted)


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "sample.jpg"
    
    try:
        image = Image.open(path).convert("RGB")
    except:
        image = Image.new('RGB', (100, 100))
        
    tags = generate_tags([image])

    print(f"Found {len(tags)} image tags:")
    for tag in tags:
        print(f"  [{tag.source:18s}] {tag.label:25s} confidence={tag.confidence:.3f} category={tag.category}")

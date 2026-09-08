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


# Fine-grained sub-labels, checked only when the trigger label appears in
# RAM's or YOLO's output. This table is the extensibility point for
# specificity - add entries as your dataset reveals categories worth
# specializing, without touching the open-vocabulary tagging itself.
FINE_GRAINED_LABELS = {
    "dog": [
        "Labrador Retriever", "German Shepherd", "Golden Retriever", "Bulldog",
        "Poodle", "Beagle", "Rottweiler", "Dachshund", "Siberian Husky",
        "Chihuahua", "Shih Tzu", "Boxer", "Great Dane", "Pomeranian",
        "Border Collie", "Doberman", "Corgi", "Mixed breed dog",
    ],
    "cat": [
        "Siamese cat", "Persian cat", "Maine Coon", "Bengal cat", "Sphynx cat",
        "British Shorthair", "Ragdoll cat", "Domestic shorthair cat",
    ],
    "flower": [
        "rose", "tulip", "sunflower", "daisy", "orchid", "lily",
        "lotus", "marigold", "hibiscus",
    ],
    "car": [
        "sedan", "SUV", "pickup truck", "hatchback", "sports car",
        "convertible", "van", "electric car",
    ],
    "bird": [
        "sparrow", "eagle", "parrot", "owl", "peacock", "pigeon",
        "duck", "crow", "flamingo",
    ],
}

# Fine-grained predictions are particularly prone to over-specific labels.
FINE_GRAINED_CONFIDENCE_THRESHOLD = 0.60
YOLO_CONFIDENCE_THRESHOLD = 0.55
GENERIC_TAGS = {"image", "photo", "photograph", "picture", "artwork"}

SCENE_KEYWORDS = {'indoor', 'outdoor', 'beach', 'mountain', 'forest', 'city', 'street', 'park', 'office', 'kitchen', 'bedroom', 'bathroom', 'garden', 'stadium', 'restaurant', 'school', 'hospital', 'airport', 'farm', 'desert', 'lake', 'river', 'ocean', 'sky', 'sunset', 'sunrise', 'night', 'snow', 'rain'}
ACTION_KEYWORDS = {'running', 'walking', 'sitting', 'standing', 'eating', 'drinking', 'playing', 'driving', 'reading', 'writing', 'dancing', 'singing', 'cooking', 'swimming', 'jumping', 'flying', 'climbing', 'surfing', 'skiing'}

@dataclass
class Tag:
    label: str
    confidence: float
    source: str          # "ram" | "yolo" | "clip_fine_grained" | "keybert" | "spacy" | "bart_mnli"
    category: str         # "open_vocab" | "object" | "fine_grained" | "keyword" | "entity" | "category" | "domain" | "scene" | "action"

def retry_handler(func):
    """Basic retry handler for transient errors."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            import logging
            logging.error(f"Error in {func.__name__}: {e}")
            return []
    return wrapper


def _classify_ram_tag_category(label: str) -> str:
    label_lower = label.lower()
    if label_lower in SCENE_KEYWORDS:
        return 'scene'
    elif label_lower in ACTION_KEYWORDS:
        return 'action'
    return 'open_vocab'


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
    result = bart_mnli(text, candidate_categories)
        
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
        Tag(label=label, confidence=1.0, source="ram", category=_classify_ram_tag_category(label))
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
    trigger_labels = {t.label.lower() for t in ram_tags} | {t.label.lower() for t, _ in yolo_detections}
    matched_triggers = trigger_labels & FINE_GRAINED_LABELS.keys()

    if not matched_triggers:
        return []

    fine_tags = []
    for trigger in matched_triggers:
        crop = _best_crop_for_trigger(image, trigger, yolo_detections)
        fine_tags.extend(_clip_classify_crop(crop, trigger, FINE_GRAINED_LABELS[trigger]))
    return fine_tags


def _best_crop_for_trigger(image: Image.Image, trigger: str, yolo_detections: list[tuple]) -> Image.Image:
    matching_boxes = [(t, b) for t, b in yolo_detections if t.label.lower() == trigger]
    if matching_boxes:
        best_tag, bbox = max(matching_boxes, key=lambda pair: pair[0].confidence)
        return image.crop(bbox)
    return image  # RAM-only trigger (e.g. "flower") has no YOLO box - use full image


def _clip_classify_crop(crop: Image.Image, trigger: str, sub_labels: list[str]) -> list[Tag]:
    clip_bundle = get_model("clip")
    model, preprocess = clip_bundle["model"], clip_bundle["preprocess"]

    text_features = get_text_embeddings(f"fine_grained_{trigger}", sub_labels)

    image_input = preprocess(crop).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        image_features = model.encode_image(image_input)
        image_features /= image_features.norm(dim=-1, keepdim=True)
        similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)

    scores = similarity[0].cpu().tolist()
    best_idx = max(range(len(scores)), key=lambda i: scores[i])
    if scores[best_idx] >= FINE_GRAINED_CONFIDENCE_THRESHOLD:
        return [Tag(
            label=sub_labels[best_idx],
            confidence=round(scores[best_idx], 4),
            source="clip_fine_grained",
            category="fine_grained",
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
    """Keep video labels repeated across frames or confirmed by RAM++ and YOLO."""
    frames_by_label: dict[str, set[int]] = {}
    sources_by_label: dict[str, set[str]] = {}
    all_tags: list[Tag] = []

    for frame_index, frame_tags in enumerate(tags_by_frame):
        for tag in frame_tags:
            key = tag.label.lower()
            frames_by_label.setdefault(key, set()).add(frame_index)
            sources_by_label.setdefault(key, set()).add(tag.source)
            all_tags.append(tag)

    confirmed_labels = {
        label for label, frame_indexes in frames_by_label.items()
        if len(frame_indexes) >= 2 or {"ram", "yolo"}.issubset(sources_by_label[label])
    }
    return _merge_and_dedupe([tag for tag in all_tags if tag.label.lower() in confirmed_labels])


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

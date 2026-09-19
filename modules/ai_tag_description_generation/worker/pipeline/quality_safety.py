import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Any
import numpy as np
from PIL import Image

from modules.ai_tag_description_generation.worker.pipeline import model_manager
from modules.ai_tag_description_generation.worker.pipeline.ocr_stt import extract_ocr_lines
from modules.ai_tag_description_generation.worker.pipeline.retry_handler import TransientError
from modules.ai_tag_description_generation.app.config import settings

logger = logging.getLogger(__name__)

@dataclass
class QualityLabels:
    blur_score: float          # Laplacian variance — lower = blurrier
    is_blurry: bool
    low_light: bool
    noisy_audio: bool
    overall_quality: str       # 'good', 'acceptable', 'poor'

@dataclass  
class PrivacySafetyLabels:
    contains_pii: bool = False
    pii_types: List[str] = field(default_factory=list)       # ['face', 'email', 'phone', 'gps', 'license_plate', 'id_number']
    pii_details: List[Dict[str, Any]] = field(default_factory=list)    # [{type, value_redacted, confidence, source}]
    faces_detected: int = 0
    nsfw_score: float = 0.0
    nsfw_flagged: bool = False
    ai_generated_score: float = 0.0
    ai_generated_flagged: bool = False
    toxicity_score: float = 0.0
    analysis_incomplete: bool = False
    analysis_errors: List[str] = field(default_factory=list)

def assess_image_quality(image: Image.Image) -> QualityLabels:
    """
    Assess blurriness and lighting of an image.
    """
    # Convert image to grayscale numpy array for analysis
    img_gray = image.convert('L')
    img_np = np.array(img_gray)
    
    # Laplacian variance for blur detection
    laplacian_var = float(np.var(np.gradient(img_np)))
    
    # Mean pixel intensity for lighting
    mean_intensity = float(np.mean(img_np))
    
    is_blurry = laplacian_var < 100.0  # Threshold
    low_light = mean_intensity < 40.0  # Threshold
    
    overall = 'good'
    if is_blurry and low_light:
        overall = 'poor'
    elif is_blurry or low_light:
        overall = 'acceptable'
        
    return QualityLabels(
        blur_score=laplacian_var,
        is_blurry=is_blurry,
        low_light=low_light,
        noisy_audio=False,
        overall_quality=overall
    )


def assess_video_quality(images: List[Image.Image]) -> QualityLabels:
    """Aggregate quality across the sampled timeline, not only frame zero."""
    if not images:
        return QualityLabels(0.0, False, False, False, 'poor')
    samples = [assess_image_quality(image) for image in images]
    blurry_count = sum(sample.is_blurry for sample in samples)
    low_light_count = sum(sample.low_light for sample in samples)
    issue_count = sum(sample.is_blurry or sample.low_light for sample in samples)
    if issue_count == len(samples):
        overall = 'poor'
    elif issue_count:
        overall = 'acceptable'
    else:
        overall = 'good'
    return QualityLabels(
        blur_score=float(np.mean([sample.blur_score for sample in samples])),
        is_blurry=blurry_count > len(samples) / 2,
        low_light=low_light_count > len(samples) / 2,
        noisy_audio=False,
        overall_quality=overall,
    )

def assess_audio_quality(rms_energy: np.ndarray, duration: float) -> QualityLabels:
    """
    Assess audio quality based on RMS energy levels.
    """
    # Simple check for silence or extreme noise
    mean_energy = float(np.mean(rms_energy)) if rms_energy.size > 0 else 0.0
    noisy = mean_energy > 0.8  # Very loud/clipped
    
    return QualityLabels(
        blur_score=1.0,
        is_blurry=False,
        low_light=False,
        noisy_audio=noisy,
        overall_quality='poor' if noisy or mean_energy < 0.01 else 'good'
    )

def detect_pii_in_text(text: str) -> PrivacySafetyLabels:
    """
    Detect PII in text using Presidio AnalyzerEngine for entity recognition,
    supplemented by regex patterns for types Presidio doesn't natively cover.
    CONSERVATIVE: Flag if any potential match.
    """
    labels = PrivacySafetyLabels()
    if not text:
        return labels

    # --- Presidio-based detection for standard PII entities ---
    try:
        analyzer = model_manager.get_model('presidio')
        presidio_entities = [
            "EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON", "CREDIT_CARD",
            "US_SSN", "IP_ADDRESS", "IBAN_CODE",
        ]
        results = analyzer.analyze(text=text, language="en", entities=presidio_entities)
        
        # Map Presidio entity types to our PII type names
        entity_type_map = {
            "EMAIL_ADDRESS": "email",
            "PHONE_NUMBER": "phone",
            "PERSON": "person_name",
            "CREDIT_CARD": "credit_card",
            "US_SSN": "id_number",
            "IP_ADDRESS": "ip_address",
            "IBAN_CODE": "iban",
        }

        for result in results:
            pii_type = entity_type_map.get(result.entity_type, result.entity_type.lower())
            labels.contains_pii = True
            if pii_type not in labels.pii_types:
                labels.pii_types.append(pii_type)
            matched_text = text[result.start:result.end]
            labels.pii_details.append({
                'type': pii_type,
                'value_redacted': matched_text[:2] + '***',
                'confidence': round(result.score, 2),
                'source': 'presidio'
            })
    except Exception as e:
        logger.warning(f"Presidio analysis failed, falling back to regex only: {e}")
        labels.analysis_incomplete = True
        labels.analysis_errors.append(f"Presidio unavailable: {type(e).__name__}")

    # --- Regex fallback for types Presidio doesn't natively cover ---
    supplemental_patterns = {
        'gps': r'\b-?\d{1,3}\.\d{4,},\s*-?\d{1,3}\.\d{4,}\b',
        'license_plate': r'\b[A-Z0-9]{3}-[A-Z0-9]{3,4}\b',
    }

    for pii_type, pattern in supplemental_patterns.items():
        matches = re.findall(pattern, text)
        if matches:
            labels.contains_pii = True
            if pii_type not in labels.pii_types:
                labels.pii_types.append(pii_type)
            for match in matches:
                labels.pii_details.append({
                    'type': pii_type,
                    'value_redacted': match[:2] + '***',
                    'confidence': 0.9,
                    'source': 'text_regex'
                })
                
    return labels

def detect_pii_in_images(images: List[Image.Image]) -> PrivacySafetyLabels:
    """
    Detect PII in images: faces via RetinaFace, and text-visible PII
    (emails, phone numbers, license plates, etc.) via OCR + Presidio/regex.
    """
    labels = PrivacySafetyLabels()
    if not images:
        return labels

    # --- Face detection via RetinaFace ---
    try:
        face_detector = model_manager.get_model('face_detector')
        total_faces = 0
        for img in images:
            try:
                img_np = np.array(img)
                detections = face_detector.detect_faces(img_np)
                if isinstance(detections, dict):
                    # RetinaFace returns a dict keyed by face_1, face_2, etc.
                    total_faces += len(detections)
                elif isinstance(detections, list):
                    total_faces += len(detections)
            except Exception as e:
                logger.warning(f"Face detection failed for an image: {e}")
                continue

        if total_faces > 0:
            labels.contains_pii = True
            labels.faces_detected = total_faces
            labels.pii_types.append('face')
            labels.pii_details.append({
                'type': 'face',
                'value_redacted': f'{total_faces} faces',
                'confidence': 0.85,
                'source': 'retinaface'
            })
    except Exception as e:
        logger.warning(f"Failed to load face detector model, skipping face detection: {e}")
        labels.analysis_incomplete = True
        labels.analysis_errors.append(f"Face detection unavailable: {type(e).__name__}")

    # --- Text-visible PII via OCR → Presidio/regex ---
    try:
        ocr_model = model_manager.get_model('paddleocr')
        ocr_texts = []
        for img in images:
            try:
                img_np = np.array(img)
                ocr_texts.extend(text for text, _conf in extract_ocr_lines(ocr_model, img_np))
            except Exception as e:
                logger.warning(f"OCR failed for an image during PII scan: {e}")
                continue

        if ocr_texts:
            combined_ocr_text = " ".join(ocr_texts)
            text_pii = detect_pii_in_text(combined_ocr_text)
            if text_pii.contains_pii:
                labels.contains_pii = True
                for pii_type in text_pii.pii_types:
                    if pii_type not in labels.pii_types:
                        labels.pii_types.append(pii_type)
                # Tag details as originating from image OCR
                for detail in text_pii.pii_details:
                    detail['source'] = f"image_ocr+{detail['source']}"
                labels.pii_details.extend(text_pii.pii_details)
    except Exception as e:
        logger.warning(f"Failed to load OCR model for image PII scan: {e}")
        labels.analysis_incomplete = True
        labels.analysis_errors.append(f"Image OCR unavailable: {type(e).__name__}")

    return labels

def assess_nsfw(images: List[Image.Image]) -> float:
    """
    NudeNet classifier for NSFW content detection.
    Returns the maximum unsafe score across all images (0.0–1.0).
    """
    if not images:
        return 0.0

    try:
        nudenet = model_manager.get_model('nudenet')
    except Exception as e:
        raise TransientError(f"Failed to load NudeNet model: {e}") from e

    max_unsafe = 0.0
    failures = 0
    for img in images:
        try:
            img_np = np.array(img)
            detections = nudenet.detect(img_np)
            # NudeDetector.detect() returns a list of dicts with 'class' and 'score'
            # Aggregate: any detection with an unsafe class contributes to the score
            for det in detections:
                score = det.get('score', 0.0)
                if score > max_unsafe:
                    max_unsafe = score
        except Exception as e:
            logger.warning(f"NSFW detection failed for an image: {e}")
            failures += 1

    if failures == len(images):
        raise TransientError("NSFW detection failed for every image")

    return max_unsafe

def assess_ai_generated(images: List[Image.Image]) -> float:
    """
    CLIP zero-shot AI-generated image detection.
    Returns the maximum AI-generated score across all images (0.0–1.0).
    """
    if not images:
        return 0.0

    try:
        detector = model_manager.get_model('ai_generated_detector')
    except Exception as e:
        raise TransientError(f"Failed to load AI-generated detector: {e}") from e

    max_score = 0.0
    failures = 0
    for img in images:
        try:
            score = detector.score(img)
            if score > max_score:
                max_score = score
        except Exception as e:
            logger.warning(f"AI-generated detection failed for an image: {e}")
            failures += 1

    if failures == len(images):
        raise TransientError("AI-generated detection failed for every image")

    return max_score


def assess_toxicity(text: str) -> float:
    """
    Detect toxic content in text using Detoxify (unbiased model).
    Returns the maximum toxicity score across all categories (0.0–1.0).
    """
    if not text or not text.strip():
        return 0.0

    try:
        toxicity_model = model_manager.get_model('toxicity')
    except Exception as e:
        raise TransientError(f"Failed to load toxicity model: {e}") from e

    try:
        results = toxicity_model.predict(text)
        # Detoxify returns dict: {toxicity, severe_toxicity, obscene, threat, insult, identity_attack, ...}
        # Take the max across all toxicity categories
        max_score = max(results.values())
        return float(max_score)
    except Exception as e:
        raise TransientError(f"Toxicity detection failed: {e}") from e


def run_quality_safety_pipeline(
    preprocessing_result: Dict[str, Any], 
    extracted_text: Dict[str, Any], 
    modality: str
) -> Tuple[QualityLabels, PrivacySafetyLabels]:
    """
    Orchestrate quality and safety checks.
    """
    # 1. Quality
    q_labels = QualityLabels(1.0, False, False, False, 'good')
    if modality == 'VIDEO':
        images = preprocessing_result.get('keyframes', [])
        if images:
            q_labels = assess_video_quality(images)
    elif modality in ('IMAGE', 'DOCUMENT'):
        images = preprocessing_result.get('images', []) or preprocessing_result.get('keyframes', [])
        if images:
            q_labels = assess_image_quality(images[0])
            
    elif modality == 'AUDIO':
        audio = preprocessing_result.get('audio_waveform', np.array([]))
        q_labels = assess_audio_quality(audio, 0)
        
    # 2. Safety (Text)
    combined_text = " ".join([
        r.text for r in extracted_text.values() if r is not None
    ])
    s_labels_text = detect_pii_in_text(combined_text)
    
    # 3. Toxicity (Text)
    try:
        toxicity_score = assess_toxicity(combined_text)
    except TransientError as exc:
        toxicity_score = 0.0
        s_labels_text.analysis_incomplete = True
        s_labels_text.analysis_errors.append(str(exc))

    # 4. Safety (Images)
    s_labels_img = PrivacySafetyLabels()
    if modality in ('IMAGE', 'VIDEO', 'DOCUMENT'):
        images = preprocessing_result.get('images', []) or preprocessing_result.get('keyframes', [])
        s_labels_img = detect_pii_in_images(images)
        try:
            s_labels_img.nsfw_score = assess_nsfw(images)
            s_labels_img.nsfw_flagged = s_labels_img.nsfw_score >= settings.NSFW_THRESHOLD
        except TransientError as exc:
            s_labels_img.analysis_incomplete = True
            s_labels_img.analysis_errors.append(str(exc))
        try:
            s_labels_img.ai_generated_score = assess_ai_generated(images)
            s_labels_img.ai_generated_flagged = s_labels_img.ai_generated_score >= settings.AI_GENERATED_THRESHOLD
        except TransientError as exc:
            s_labels_img.analysis_incomplete = True
            s_labels_img.analysis_errors.append(str(exc))

    # Merge Safety Labels
    merged_s_labels = PrivacySafetyLabels(
        contains_pii=s_labels_text.contains_pii or s_labels_img.contains_pii,
        pii_types=list(set(s_labels_text.pii_types + s_labels_img.pii_types)),
        pii_details=s_labels_text.pii_details + s_labels_img.pii_details,
        faces_detected=s_labels_img.faces_detected,
        nsfw_score=s_labels_img.nsfw_score,
        nsfw_flagged=s_labels_img.nsfw_flagged,
        ai_generated_score=s_labels_img.ai_generated_score,
        ai_generated_flagged=s_labels_img.ai_generated_flagged,
        toxicity_score=toxicity_score,
        analysis_incomplete=s_labels_text.analysis_incomplete or s_labels_img.analysis_incomplete,
        analysis_errors=s_labels_text.analysis_errors + s_labels_img.analysis_errors,
    )
    
    return q_labels, merged_s_labels

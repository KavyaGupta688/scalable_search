import logging
import json
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import numpy as np
from PIL import Image

from modules.ai_tag_description_generation.worker.pipeline.retry_handler import TransientError, DataQualityError, with_retry
from modules.ai_tag_description_generation.worker.pipeline import model_manager

logger = logging.getLogger(__name__)

@dataclass
class ExtractionResult:
    text: str
    source: str          # 'paddleocr', 'whisper-large-v3', 'native_parser'
    language: str         # detected or assumed language code
    confidence: float     # 0.0-1.0


def extract_ocr_lines(model, image: np.ndarray) -> list[tuple[str, float]]:
    """Return OCR text/confidence pairs from PaddleOCR v2 or v3."""
    # PaddleOCR v3 uses ``predict`` and returns mapping-like OCRResult objects.
    if hasattr(model, "predict"):
        lines: list[tuple[str, float]] = []
        for prediction in model.predict(image):
            data = prediction
            if not isinstance(data, dict):
                data = getattr(prediction, "json", prediction)
                data = data() if callable(data) else data
                if isinstance(data, str):
                    data = json.loads(data)
            if isinstance(data, dict):
                data = data.get("res", data)
                texts = data.get("rec_texts", [])
                scores = data.get("rec_scores", [])
                lines.extend((str(text), float(score)) for text, score in zip(texts, scores))
        return lines

    # PaddleOCR v2 legacy result format.
    result = model.ocr(image, cls=True)
    if not result or not result[0]:
        return []
    return [(str(line[1][0]), float(line[1][1])) for line in result[0]]

def run_ocr(images: List[Image.Image]) -> ExtractionResult:
    """
    Run PaddleOCR on images to extract text.
    """
    if not images:
        raise DataQualityError("No images provided for OCR.")
        
    try:
        model = model_manager.get_model('paddleocr')
    except Exception as e:
        raise TransientError(f"Failed to load OCR model: {str(e)}")

    all_texts = []
    total_confidence = 0.0
    count = 0

    for img in images:
        try:
            # PaddleOCR v3 expects HxWx3 input. Direct callers can pass a
            # grayscale/P-mode receipt image, unlike the preprocessing stage
            # which already normalizes images to RGB.
            img_np = np.array(img.convert("RGB"))
            for text, conf in extract_ocr_lines(model, img_np):
                all_texts.append(text)
                total_confidence += conf
                count += 1
        except Exception as e:
            # Could be a bad image (data quality) or a transient model crash
            raise TransientError(f"OCR processing failed for image: {str(e)}")
            
    if count == 0:
        return ExtractionResult(text="", source="paddleocr", language="en", confidence=0.0)
        
    avg_conf = total_confidence / count
    final_text = " ".join(all_texts)
    
    return ExtractionResult(
        text=final_text,
        source="paddleocr",
        language="en", # Default for now
        confidence=avg_conf
    )

def run_speech_to_text(waveform: np.ndarray, sample_rate: int = 16000) -> ExtractionResult:
    """
    Run Whisper on audio waveform to extract text.
    """
    if waveform.size == 0 or np.all(waveform == 0):
        raise DataQualityError("Audio waveform is empty or entirely silent.")
        
    try:
        model = model_manager.get_model('whisper')
    except Exception as e:
        raise TransientError(f"Failed to load Whisper model: {str(e)}")

    try:
        # Whisper transcription via model_manager
        result = model.transcribe(
            waveform,
            fp16=model_manager.DEVICE == "cuda",
            temperature=0,
            condition_on_previous_text=False,
        )
        
        text = result.get('text', '').strip()
        language = result.get('language', 'en')
        
        # Calculate average segment confidence
        segments = result.get('segments', [])
        if segments:
            speech_segments = [
                segment for segment in segments
                if float(segment.get('no_speech_prob', 0.0)) < 0.6
            ]
            if not speech_segments:
                return ExtractionResult(
                    text="", source="whisper-large-v3", language=language, confidence=0.0
                )
            # Rebuild from speech-like segments so music/silence hallucinations
            # in Whisper's aggregate text do not enter tags and captions.
            text = " ".join(
                str(segment.get('text', '')).strip()
                for segment in speech_segments
                if str(segment.get('text', '')).strip()
            )
            probabilities = [
                math.exp(min(0.0, float(segment.get('avg_logprob', -0.7))))
                * (1.0 - float(segment.get('no_speech_prob', 0.0)))
                for segment in speech_segments
            ]
            conf = sum(probabilities) / len(probabilities)
        else:
            conf = 0.0
            
        return ExtractionResult(
            text=text,
            source="whisper-large-v3",
            language=language,
            confidence=conf
        )
    except Exception as e:
        raise TransientError(f"STT processing failed: {str(e)}")

def extract_native_text(doc_text: str, file_format: str) -> ExtractionResult:
    """
    Passthrough for natively extracted document text.
    """
    if not doc_text:
        return ExtractionResult(text="", source="native_parser", language="en", confidence=0.0)
        
    return ExtractionResult(
        text=doc_text.strip(),
        source="native_parser",
        language="en",
        confidence=0.95
    )

def extract_text_for_modality(
    preprocessing_result: Dict[str, Any], 
    modality: str
) -> Dict[str, Optional[ExtractionResult]]:
    """
    Route extraction tasks based on data modality.
    """
    results: Dict[str, Optional[ExtractionResult]] = {
        'ocr_text': None,
        'transcribed_text': None,
        'native_document_text': None
    }
    
    if modality == 'IMAGE':
        images = preprocessing_result.get('images', [])
        if images:
            results['ocr_text'] = with_retry(run_ocr, images)
            
    elif modality == 'VIDEO':
        images = preprocessing_result.get('keyframes', [])
        if images:
            results['ocr_text'] = with_retry(run_ocr, images)
            
        audio = preprocessing_result.get('audio_waveform')
        if audio is not None:
            results['transcribed_text'] = with_retry(run_speech_to_text, audio)
            
    elif modality == 'AUDIO':
        audio = preprocessing_result.get('audio_waveform')
        if audio is not None:
            results['transcribed_text'] = with_retry(run_speech_to_text, audio)
            
    elif modality == 'DOCUMENT':
        native_text = preprocessing_result.get('text', '')
        if native_text:
            results['native_document_text'] = extract_native_text(native_text, 'pdf')
            
        if preprocessing_result.get('needs_ocr'):
            images = preprocessing_result.get('pages_as_images', [])
            if images:
                results['ocr_text'] = with_retry(run_ocr, images)
                
    elif modality == 'CSV':
        columns = preprocessing_result.get('columns', [])
        sample_data = preprocessing_result.get('sample_data', '')
        text = f"Columns: {', '.join(columns)}. Data: {sample_data}"
        results['native_document_text'] = extract_native_text(text, 'csv')
        
    return results

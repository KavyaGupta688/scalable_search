import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import numpy as np
from PIL import Image

from worker.pipeline.retry_handler import TransientError, DataQualityError, with_retry
from worker.pipeline import model_manager

logger = logging.getLogger(__name__)

@dataclass
class ExtractionResult:
    text: str
    source: str          # 'paddleocr', 'whisper-large-v3', 'native_parser'
    language: str         # detected or assumed language code
    confidence: float     # 0.0-1.0

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
            # Convert PIL image to numpy array as expected by PaddleOCR
            img_np = np.array(img)
            # result structure: list of [bbox, (text, confidence)]
            result = model.ocr(img_np, cls=True)
            
            if not result or not result[0]:
                continue
                
            for line in result[0]:
                text, conf = line[1]
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
        result = model.transcribe(waveform)
        
        text = result.get('text', '').strip()
        language = result.get('language', 'en')
        
        # Calculate average segment confidence
        segments = result.get('segments', [])
        if segments:
            conf = sum(s.get('confidence', 0.5) for s in segments) / len(segments)
        else:
            conf = 0.8 # Fallback
            
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

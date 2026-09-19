import logging
from typing import Dict, List, Tuple, Any

from modules.ai_tag_description_generation.app.config import settings

logger = logging.getLogger(__name__)

def _validate_required_fields(record: Dict[str, Any]) -> List[str]:
    """Check presence and length of required fields."""
    warnings = []
    
    descs = record.get('descriptions', {})
    if not descs.get('short_description'):
        warnings.append("Missing short_description")
    elif len(descs['short_description']) < 10:
        warnings.append("short_description is too short (< 10 chars)")
        
    if not record.get('generated_tags'):
        warnings.append("No tags generated")
        
    return warnings

def _check_safety_flags(record: Dict[str, Any]) -> List[str]:
    """Return list of review reasons based on safety labels."""
    reasons = []
    safety = record.get('safety_labels', {})
    
    if safety.get('nsfw_flagged'):
        reasons.append("NSFW content detected")
    if safety.get('contains_pii'):
        pii_types = safety.get('pii_types', [])
        # High sensitivity PII
        if any(t in pii_types for t in ['id_number', 'face', 'license_plate']):
            reasons.append(f"High sensitivity PII detected: {pii_types}")
    if safety.get('analysis_incomplete'):
        reasons.append("One or more safety checks did not complete")
    if safety.get('toxicity_score', 0.0) >= settings.TOXICITY_THRESHOLD:
        reasons.append("Toxic content detected")
            
    return reasons

def validate_and_score(metadata_record: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """
    Score metadata quality and determine final task status.
    """
    # 1. Tags confidence
    tags = metadata_record.get('generated_tags', [])
    if tags:
        tag_conf = sum(t.get('confidence', 0) for t in tags) / len(tags)
    else:
        tag_conf = 0.0
        
    # 2. Descriptions confidence
    descs = metadata_record.get('descriptions', {})
    short_desc = descs.get('short_description', '')
    if short_desc and len(short_desc) > 10:
        desc_conf = 1.0
    elif short_desc:
        desc_conf = 0.5
    else:
        desc_conf = 0.0
        
    # 3. Extracted text confidence
    ext_text = metadata_record.get('extracted_text', {})
    text_confs = [v.get('confidence', 0) for v in ext_text.values()]
    if text_confs:
        text_conf = max(text_confs)
    else:
        text_conf = 0.0
        
    # 4. Quality/Safety (static 1.0 for now)
    quality = metadata_record.get('quality_labels', {})
    safety = metadata_record.get('safety_labels', {})
    qual_conf = 0.5 if quality.get('overall_quality') == 'poor' else 1.0
    safe_conf = 0.0 if safety.get('analysis_incomplete') else 1.0
    
    # 5. Aggregate Score
    aggregate = (
        (tag_conf * 0.3) +
        (desc_conf * 0.3) +
        (text_conf * 0.2) +
        (qual_conf * 0.1) +
        (safe_conf * 0.1)
    )
    
    metadata_record['confidence_scores'] = {
        'tags': tag_conf,
        'descriptions': desc_conf,
        'extracted_text': text_conf,
        'aggregate': aggregate
    }
    
    # Validation & Routing
    warnings = _validate_required_fields(metadata_record)
    review_reasons = _check_safety_flags(metadata_record)
    
    final_status = 'completed'
    
    if review_reasons or aggregate < settings.CONFIDENCE_THRESHOLD_REVIEW:
        final_status = 'needs_review'
    elif aggregate < settings.CONFIDENCE_THRESHOLD_COMPLETED or warnings:
        if aggregate < 0.1 or (not tags and not short_desc):
            final_status = 'failed_terminal'
        else:
            final_status = 'partial'
            
    return metadata_record, final_status

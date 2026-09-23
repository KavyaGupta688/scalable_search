import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

def _normalize_tag(label: str) -> str:
    """Normalize casing and whitespace without corrupting valid words."""
    return " ".join(label.casefold().split())

def _deduplicate_tags(tags: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge tags by normalized label, keeping highest confidence."""
    merged = {}
    for tag in tags:
        norm = _normalize_tag(tag.get('tag', ''))
        if not norm:
            continue
            
        source = tag.get('source_model', 'unknown')
        if norm not in merged:
            merged[norm] = {**tag, 'sources': {source}}
            continue

        existing = merged[norm]
        sources = set(existing.get('sources', set()))
        sources.add(source)
        if tag.get('confidence', 0) > existing.get('confidence', 0):
            merged[norm] = {**tag, 'sources': sources}
        else:
            existing['sources'] = sources
            
    return list(merged.values())

def _resolve_conflicts(tags: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Boost tags confirmed by multiple models."""
    for tag in tags:
        sources = tag.get('sources', set())
        # If multiple models agree, boost confidence
        if len(sources) > 1:
            tag['confidence'] = min(1.0, tag.get('confidence', 0.5) * 1.2)
        
        # Cleanup internal keys
        if 'sources' in tag:
            del tag['sources']
            
    return tags

def fuse_metadata(
    tags: List[Dict[str, Any]], 
    captions: Dict[str, str], 
    extracted_text: Dict[str, Any], 
    quality_labels: Any, 
    safety_labels: Any, 
    modality: str, 
    model_versions: Dict[str, str],
    technical: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Normalize and merge all metadata into final schema.
    """
    
    # 1. Process tags
    normalized_tags = _deduplicate_tags(tags)
    resolved_tags = _resolve_conflicts(normalized_tags)
    
    final_tags = []
    for t in resolved_tags:
        final_tags.append({
            'tag': _normalize_tag(t.get('tag', '')),
            'category': t.get('category', 'general'),
            'source_model': t.get('source_model', 'unknown'),
            'confidence': float(t.get('confidence', 0.5))
        })

    # 2. Process extracted text
    text_dict = {}
    for key, result in extracted_text.items():
        if result:
            text_dict[key] = {
                'text': result.text,
                'language': result.language,
                'confidence': result.confidence
            }
            
    # 3. Construct payload
    payload = {
        'generated_tags': final_tags,
        'descriptions': {
            'short_description': captions.get('short', ''),
            'long_description': captions.get('long', ''),
            'search_optimized': captions.get('search', ''),
            'accessibility_alt': captions.get('alt', '')
        },
        'extracted_text': text_dict,
        'quality_labels': {
            'blur_score': quality_labels.blur_score,
            'overall_quality': quality_labels.overall_quality,
            'is_blurry': quality_labels.is_blurry,
            'low_light': quality_labels.low_light,
            'noisy_audio': quality_labels.noisy_audio,
            # Pixel size / duration / fps, read by the search indexer for resolution filters.
            'technical': dict(technical or {}),
        },
        'safety_labels': {
            'contains_pii': safety_labels.contains_pii,
            'nsfw_flagged': safety_labels.nsfw_flagged,
            'ai_generated_flagged': safety_labels.ai_generated_flagged,
            'pii_types': safety_labels.pii_types,
            'faces_detected': safety_labels.faces_detected,
            'nsfw_score': safety_labels.nsfw_score,
            'ai_generated_score': safety_labels.ai_generated_score,
            'toxicity_score': safety_labels.toxicity_score,
            'analysis_incomplete': safety_labels.analysis_incomplete,
            'analysis_errors': safety_labels.analysis_errors,
        },
        'restricted_metadata': {
            'pii_details': safety_labels.pii_details,
        },
        'modality': modality,
        'models_used': model_versions
    }
    
    return payload

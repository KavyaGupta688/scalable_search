import re
from typing import Dict, Any, Optional, List
from app.utils.query_normalizer import normalize_text, tokenize, extract_significant_tokens
from app.schemas.filters import SearchFilters

class QueryProcessor:
    """
    Processes, cleans, and analyzes search queries, extracting intent and inline filter hints.
    """
    def process_query(self, raw_query: str, current_filters: Optional[SearchFilters] = None) -> Dict[str, Any]:
        cleaned_text = normalize_text(raw_query)
        tokens = tokenize(raw_query)
        keywords = extract_significant_tokens(raw_query)
        
        # Check for inline entity/type mentions if filters aren't already set
        inferred_filters = current_filters.model_copy() if current_filters else SearchFilters()
        
        type_keywords = {
            "image": "image", "photo": "image", "picture": "image",
            "video": "video", "footage": "video", "recording": "video",
            "audio": "audio", "voice": "audio", "sound": "audio", "speech": "audio",
            "document": "document", "doc": "document", "pdf": "document", "report": "document",
            "csv": "csv", "table": "csv", "data": "csv"
        }
        
        category_keywords = {
            "nature": "Nature", "forest": "Nature", "mountain": "Nature",
            "technology": "Technology", "robot": "Technology", "ai": "Technology", "software": "Technology",
            "medical": "Medical", "health": "Medical", "doctor": "Medical", "x-ray": "Medical",
            "vehicle": "Vehicles", "car": "Vehicles", "satellite": "Vehicles", "plane": "Vehicles",
            "architecture": "Architecture", "building": "Architecture", "bridge": "Architecture",
            "business": "Business", "finance": "Business", "meeting": "Business",
            "people": "People", "worker": "People", "team": "People",
            "sports": "Sports", "football": "Sports", "soccer": "Sports",
            "food": "Food", "agriculture": "Food", "crop": "Food",
            "education": "Education", "student": "Education", "school": "Education",
            "animals": "Animals", "wildlife": "Animals", "bird": "Animals",
            "abstract": "Abstract", "pattern": "Abstract"
        }

        # Intent detection
        is_question = any(cleaned_text.startswith(w) for w in ["what", "where", "how", "show", "find", "give"])

        return {
            "raw_query": raw_query,
            "normalized_query": cleaned_text,
            "tokens": tokens,
            "keywords": keywords,
            "is_natural_language": len(tokens) > 2 or is_question,
            "filters": inferred_filters
        }

_query_processor = QueryProcessor()

def get_query_processor() -> QueryProcessor:
    return _query_processor

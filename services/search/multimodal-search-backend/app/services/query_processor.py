import re
from typing import Dict, Any, Optional, List
from app.utils.query_normalizer import normalize_text, tokenize, extract_significant_tokens
from app.schemas.filters import SearchFilters

class QueryProcessor:
    """
    Processes and cleans search queries, and detects type/category intent
    hints (e.g. "satellite" implies category=Vehicles). Detected hints are
    returned as a *suggestion* only (see process_query's "suggested_filters"
    key) - never silently merged into the filters actually used to search,
    since an ambiguous or wrong guess would invisibly hide valid results
    with no indication to the user why. The caller decides whether/how to
    surface the suggestion (e.g. a dismissible filter chip in the UI).
    """

    TYPE_KEYWORDS: Dict[str, str] = {
        "image": "image", "photo": "image", "picture": "image",
        "video": "video", "footage": "video", "recording": "video",
        "audio": "audio", "voice": "audio", "sound": "audio", "speech": "audio",
        "document": "document", "doc": "document", "pdf": "document", "report": "document",
        "csv": "csv", "table": "csv", "data": "csv"
    }

    CATEGORY_KEYWORDS: Dict[str, str] = {
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

    def process_query(self, raw_query: str, current_filters: Optional[SearchFilters] = None) -> Dict[str, Any]:
        cleaned_text = normalize_text(raw_query)
        tokens = tokenize(raw_query)
        keywords = extract_significant_tokens(raw_query)

        # Intent detection
        is_question = any(cleaned_text.startswith(w) for w in ["what", "where", "how", "show", "find", "give"])

        return {
            "raw_query": raw_query,
            "normalized_query": cleaned_text,
            "tokens": tokens,
            "keywords": keywords,
            "is_natural_language": len(tokens) > 2 or is_question,
            "suggested_filters": self._detect_suggested_filters(tokens, current_filters)
        }

    def _detect_suggested_filters(
        self,
        tokens: List[str],
        current_filters: Optional[SearchFilters]
    ) -> Optional[SearchFilters]:
        """
        Scans query tokens for type/category intent hints via exact
        whole-word matches (never substring matches, to avoid false hits
        like "ai" inside "again"). Skips a dimension the caller has already
        filtered on explicitly - no point suggesting what's already applied.
        Returns None (not an empty SearchFilters) when nothing was detected,
        so callers can cheaply check `if suggested_filters:`.
        """
        matched_types = sorted({self.TYPE_KEYWORDS[t] for t in tokens if t in self.TYPE_KEYWORDS})
        matched_categories = sorted({self.CATEGORY_KEYWORDS[t] for t in tokens if t in self.CATEGORY_KEYWORDS})

        already_has_type = bool(current_filters and current_filters.file_types)
        already_has_category = bool(current_filters and current_filters.categories)

        suggested_types = matched_types if (matched_types and not already_has_type) else None
        suggested_categories = matched_categories if (matched_categories and not already_has_category) else None

        if not suggested_types and not suggested_categories:
            return None

        return SearchFilters(file_types=suggested_types, categories=suggested_categories)

_query_processor = QueryProcessor()

def get_query_processor() -> QueryProcessor:
    return _query_processor

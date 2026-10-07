import re
import unicodedata
from typing import List, Set

STOP_WORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", 
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", 
    "by", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from", 
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him", 
    "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me", 
    "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once", "only", 
    "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she", 
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves", 
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", 
    "up", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom", 
    "why", "with", "would", "you", "your", "yours", "yourself", "yourselves"
}

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    text = re.sub(r"[^\w\s-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def escape_like(text: str) -> str:
    """Escapes LIKE wildcards so user input matches literally (use with ESCAPE '\\')."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def tokenize(text: str) -> List[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    tokens = re.findall(r"[^\W_]+", normalized, flags=re.UNICODE)
    return tokens

def extract_significant_tokens(text: str) -> List[str]:
    tokens = tokenize(text)
    return [t for t in tokens if t not in STOP_WORDS]

def normalize_query_for_trending(query: str) -> str:
    """
    Normalizes similar queries to group variations (e.g. 'coal mining!', 'Coal Mining', 'coal-mining' -> 'coal mining')
    """
    normalized = normalize_text(query)
    return normalized


def term_variants(term):
    """The literal word forms a term matches: itself plus conservative English plurals.

    term_pattern turns these into a regex; the full-text prefilter turns them into lexemes,
    so both always agree on which words a term covers.
    """
    if term in ('person', 'people'):
        return ['child', 'children', 'man', 'men', 'people', 'person', 'woman', 'women']
    for group in [('man', 'men'), ('woman', 'women'), ('person', 'people'), ('child', 'children')]:
        if term in group:
            return list(group)
    base = term
    if term.isascii() and term.isalpha() and len(term) > 3:
        if term.endswith('ies'):
            return sorted({term, term[:-3] + 'y'})
        if term.endswith('s') and not term.endswith(('ss', 'us', 'is')):
            base = term[:-1]
    variants = {term, base}
    if base.isascii() and base.isalpha() and len(base) > 2:
        variants.add(base + 's')
        if base.endswith('y'):
            variants.add(base[:-1] + 'ies')
    return sorted(variants)


def term_pattern(term):
    """Conservative, symmetric English plurals; preserve identifiers and other scripts."""
    if term in ('person', 'people'):
        return '(?:person|people|man|men|woman|women|child|children)'
    for group in [('man', 'men'), ('woman', 'women'), ('person', 'people'), ('child', 'children')]:
        if term in group:
            return '(?:' + '|'.join(group) + ')'
    variants = term_variants(term)
    if term.isascii() and term.isalpha() and len(term) > 3 and term.endswith('ies'):
        return '(?:' + re.escape(term) + '|' + re.escape(term[:-3] + 'y') + ')'
    return '(?:' + '|'.join(re.escape(value) for value in variants) + ')'


def retrieval_query(query):
    """Remove request wording, while retaining descriptive modifiers and negations."""
    return re.sub(r'^\s*(?:please\s+)?(?:show\s+me|find(?:\s+me)?|search\s+for|give\s+me)\s+', '', query, flags=re.I).strip()


def search_intent(query):
    """Recognize a trailing explicit exclusion, without discarding it as a stop word."""
    query = retrieval_query(query)
    parts = re.split(r"\b(?:without|excluding|except|but not|not)\s+", query, maxsplit=1, flags=re.I)
    positive = parts[0].strip()
    excluded = extract_significant_tokens(parts[1]) if len(parts) > 1 else []
    return positive, excluded

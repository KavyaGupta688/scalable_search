"""Local query/document relevance verification, shared by results, facets and downloads."""
from functools import lru_cache
from threading import Lock

MODEL = 'cross-encoder/ms-marco-MiniLM-L6-v2'
REVISION = 'ce0834f22110de6d9222af7a7a03628121708969'
_lock = Lock()
_scores = {}


@lru_cache(maxsize=1)
def bundle():
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL, revision=REVISION, use_safetensors=True).eval()
    return tokenizer, model


def _terms(query):
    from app.utils.query_normalizer import extract_significant_tokens, tokenize, retrieval_query
    query = retrieval_query(query)
    return extract_significant_tokens(query) or tokenize(query)


def _matches(term, value):
    import re
    from app.utils.query_normalizer import term_pattern
    return bool(re.search(r'(?<![^\W_])' + term_pattern(term) + r'(?![^\W_])', value, re.I))


def passages(query, file):
    """Keep primary descriptions and query-bearing windows of longer extracted text."""
    terms = _terms(query)
    title = str(getattr(file, 'title', '') or '')
    primary = ' '.join(dict.fromkeys(str(getattr(file, field, '') or '') for field in ('title', 'description', 'caption', 'file_name')))
    first = ' '.join(primary.split()[:160])
    windows = []
    fields = ['description', 'caption', 'ocr_text', 'transcript']
    if not (getattr(file, 'description', None) or getattr(file, 'caption', None)):
        fields.append('content_summary')
    for field in fields:
        words = str(getattr(file, field, '') or '').split()
        for start in range(0, len(words), 100):
            chunk = ' '.join(words[start:start + 140])
            coverage = sum(_matches(term, chunk) for term in terms)
            if coverage:
                windows.append((coverage, title + '\n' + chunk))
    windows.sort(key=lambda entry: -entry[0])
    return list(dict.fromkeys([first] + [chunk for _, chunk in windows]))[:3]


def direct_name_match(query, file):
    from app.utils.query_normalizer import tokenize
    terms = _terms(query)
    if not terms or set(tokenize(query)) & {'no', 'not', 'without', 'except', 'excluding'}:
        return False
    # Short entity queries need lexical evidence: the QA model is poorly calibrated
    # for single nouns. Use descriptions, never noisy generated tag lists.
    fields = ('title', 'file_name', 'description', 'caption') if len(terms) <= 2 else ('title', 'file_name')
    return any(all(_matches(term, str(getattr(file, field, '') or '')) for term in terms) for field in fields)


def excluded_match(terms, file):
    # Exclusion is checked against descriptive/source text, not noisy tag guesses.
    return any(all(_matches(term, str(getattr(file, field, '') or '')) for term in terms)
               for field in ('title', 'file_name', 'description', 'caption', 'ocr_text', 'transcript'))


def _shared_key(pair):
    import hashlib
    digest = hashlib.sha256((pair[0] + '\0' + pair[1]).encode()).hexdigest()
    return 'search:rel:' + REVISION[:12] + ':' + digest


def _shared_scores(pairs):
    """Pair scores other replicas already computed. The model is deterministic, so a
    shared score is the score this replica would compute; Redis being down just
    means computing locally."""
    from app.clients.embedding_client import _redis, _redis_state
    import time
    client = _redis()
    if client is None:
        return {}
    try:
        values = client.mget([_shared_key(pair) for pair in pairs])
    except Exception:
        _redis_state['down_until'] = time.monotonic() + 30
        return {}
    return {pair: float(value) for pair, value in zip(pairs, values) if value is not None}


def _store_shared(scores):
    import os
    import time
    from app.clients.embedding_client import _redis, _redis_state
    client = _redis()
    if client is None:
        return
    ttl = int(os.getenv('SEARCH_RELEVANCE_CACHE_TTL_SECONDS', '86400'))
    try:
        pipe = client.pipeline(transaction=False)
        for pair, score in scores.items():
            pipe.set(_shared_key(pair), repr(float(score)), ex=ttl)
        pipe.execute()
    except Exception:
        _redis_state['down_until'] = time.monotonic() + 30


def rerank(query, items, files):
    if query.strip().lower() in ('', '*', 'all') or not items:
        return items
    import torch
    from app.core.config import get_settings
    settings = get_settings()
    # Only deterministic pair scores are cached. Visibility and filters are always rechecked.
    from app.utils.query_normalizer import search_intent
    query, excluded = search_intent(query)
    if not query:
        return []
    items = [item for item in items if item.id in files]
    import re
    if re.fullmatch(r'[^\s/\\]+\.[a-zA-Z0-9]{2,5}', query):
        # A complete filename is an identifier, not a request for similar assets.
        items = [item for item in items if str(getattr(files[item.id], 'file_name', '')).casefold() == query.casefold()]
    if excluded:
        items = [item for item in items if not excluded_match(excluded, files[item.id])]
    groups = [[(query, text) for text in list(dict.fromkeys(([item.matched_passage] if item.matched_passage else []) + passages(query, files[item.id])))[:4]] for item in items]
    pairs = [pair for group in groups for pair in group]
    with _lock:
        missing = list(dict.fromkeys(pair for pair in pairs if pair not in _scores))
    shared = _shared_scores(missing) if missing else {}
    with _lock:
        _scores.update(shared)
        missing = [pair for pair in missing if pair not in _scores]
        computed = {}
        if missing:
            tokenizer, model = bundle()
            for offset in range(0, len(missing), 16):
                batch = missing[offset:offset + 16]
                encoded = tokenizer(batch, padding=True, truncation=True, max_length=256, return_tensors='pt')
                with torch.inference_mode():
                    scores = model(**encoded).logits.flatten().tolist()
                computed.update(zip(batch, scores))
            _scores.update(computed)
        values = [max(_scores[pair] for pair in group) for group in groups]
        while len(_scores) > 4096:
            del _scores[next(iter(_scores))]
    if computed:
        _store_shared(computed)
    kept = []
    for item, score in zip(items, values):
        supported = direct_name_match(query, files[item.id])
        # Visual evidence must survive a text-only verifier that cannot see pixels.
        visual = item.visual_similarity is not None and item.visual_similarity >= settings.VISUAL_ACCEPT_MIN
        semantic = item.semantic_similarity is not None and item.semantic_similarity >= settings.SEMANTIC_ACCEPT_MIN
        evidence_score = max((item.visual_similarity - settings.VISUAL_ACCEPT_MIN) * 20 if visual else -100,
                             (item.semantic_similarity - settings.SEMANTIC_ACCEPT_MIN) * 12 if semantic else -100)
        item.relevance_score = max(score, evidence_score, 0.0 if supported else -100)
        if score >= settings.RELEVANCE_MIN_LOGIT or supported or visual or semantic:
            kept.append(item)
    # A cross-encoder logit is not a probability. Keep it internal for diagnostics.
    return sorted(kept, key=lambda item: (-item.relevance_score, -item.rrf_score, item.id))

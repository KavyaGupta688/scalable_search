from types import SimpleNamespace
import pytest
from app.services import relevance_service as relevance
from app.utils.rrf import FusionResult, RankedItem, reciprocal_rank_fusion
from app.repositories.file_repository import conditions


def test_model_scores_reject_weak_neighbours(monkeypatch):
    files = {key: SimpleNamespace(title=key) for key in ['good', 'unrelated', 'okay']}
    monkeypatch.setattr(relevance, '_scores', {('query', text): score
        for (key, file), score in zip(files.items(), [3.0, -5.0, -1.0])
        for text in relevance.passages('query', file)})
    hits = [FusionResult(id=key, rrf_score=.01) for key in files]
    hits.append(FusionResult(id='missing', rrf_score=1))
    assert [r.id for r in relevance.rerank('query', hits, files)] == ['good', 'okay']


def test_browse_does_not_load_model(monkeypatch):
    monkeypatch.setattr(relevance, 'bundle', lambda: pytest.fail('Unexpected model load'))
    hits = [FusionResult(id='file', rrf_score=1)]
    assert relevance.rerank('*', hits, {}) == hits


def test_short_entity_queries_use_descriptions_not_tags():
    basketball = SimpleNamespace(title='Basketball', description='Two young men playing on a court')
    noisy = SimpleNamespace(title='Purple background', tags=['man'], content_summary='man stool')
    assert relevance.direct_name_match('man', basketball)
    assert relevance.direct_name_match('men', basketball)
    assert not relevance.direct_name_match('man', noisy)
    assert not relevance.direct_name_match('man', SimpleNamespace(description='A woman standing'))
    assert not relevance.direct_name_match('without a man', basketball)


def test_request_wording_preserves_negation():
    from app.utils.query_normalizer import retrieval_query
    assert retrieval_query('Please show me a dog') == 'a dog'
    assert retrieval_query('find me a dog without a ball') == 'a dog without a ball'


def test_late_transcript_matches_survive_window_selection():
    file = SimpleNamespace(title='Interview', transcript=('opening ' * 1000) + 'quantum cryptography research')
    chunks = relevance.passages('quantum cryptography', file)
    assert any('quantum cryptography' in chunk for chunk in chunks)
    assert len(chunks) <= 3


def test_unicode_identifiers_and_plural_matching():
    from app.utils.query_normalizer import tokenize
    assert tokenize('caf\u00e9 \u6771\u4eac image_png_001.png') == ['caf\u00e9', '\u6771\u4eac', 'image', 'png', '001', 'png']
    for term, text in [('dogs', 'dog'), ('dog', 'dogs'), ('women', 'woman'), ('man', 'men')]:
        assert relevance._matches(term, text)
    assert not relevance._matches('ball', 'balloon')
    assert relevance._matches('001', 'image_001.png')


def test_punctuation_does_not_become_browse():
    clauses, tokens, _ = conditions('!!!', None)
    assert not tokens
    assert str(clauses[-1]) == 'false'


def test_disabled_branches_and_invalid_settings():
    from app.schemas.search import SearchRequest, DownloadPlanRequest
    kw = [RankedItem(id='keyword', rank=1, raw_score=1)]
    vec = [RankedItem(id='vector', rank=1, raw_score=1)]
    assert [r.id for r in reciprocal_rank_fusion(kw, vec, keyword_weight=0)] == ['vector']
    assert [r.id for r in reciprocal_rank_fusion(kw, vec, vector_weight=0)] == ['keyword']
    for schema in (SearchRequest, DownloadPlanRequest):
        with pytest.raises(ValueError):
            schema(query='dog', rrf_k=0)
        with pytest.raises(ValueError):
            schema(query='dog', keyword_weight=0, vector_weight=0)


def test_keyword_and_hybrid_candidate_conditions():
    from sqlalchemy.dialects import postgresql
    clauses, tokens, _ = conditions('red ball', None)
    assert tokens == ['red', 'ball']
    assert ' AND ' in str(clauses[-1].compile(dialect=postgresql.dialect()))
    loose, _, _ = conditions('red ball', None, match_all=False)
    assert ' AND ' not in str(loose[-1].compile(dialect=postgresql.dialect()))


def test_exclusions_remove_contradictory_results_before_scoring(monkeypatch):
    from app.utils.query_normalizer import search_intent
    assert search_intent('show me dogs without a ball') == ('dogs', ['ball'])
    files = {'ball': SimpleNamespace(title='Dog with a ball'), 'guide': SimpleNamespace(title='Dog care guide')}
    monkeypatch.setattr(relevance, '_scores', {('dog', text): -7.0 for text in relevance.passages('dog', files['guide'])})
    hits = [FusionResult(id=key, rrf_score=.01) for key in files]
    assert [r.id for r in relevance.rerank('dog without a ball', hits, files)] == ['guide']


def test_filename_lookup_does_not_return_similar_filenames(monkeypatch):
    file = SimpleNamespace(title='Asset', file_name='image_001.png')
    files = {'exact': file, 'other': SimpleNamespace(title='Asset', file_name='image_002.png')}
    monkeypatch.setattr(relevance, '_scores', {('image_001.png', text): -7.0 for text in relevance.passages('image_001.png', file)})
    hits = [FusionResult(id=key, rrf_score=.01) for key in files]
    assert [r.id for r in relevance.rerank('image_001.png', hits, files)] == ['exact']


def test_noisy_summary_is_not_an_independent_description():
    file = SimpleNamespace(title='Purple background', description='A solid purple background', content_summary='man stool')
    assert all('man' not in chunk for chunk in relevance.passages('man', file))


@pytest.mark.asyncio
async def test_zero_weight_branch_is_not_called(monkeypatch):
    from unittest.mock import AsyncMock
    from app.services.hybrid_search_service import HybridSearchService
    text = SimpleNamespace(search=AsyncMock(return_value=([], 0, {})))
    vector = SimpleNamespace(search_by_query=AsyncMock(side_effect=AssertionError('Disabled branch called')))
    service = HybridSearchService(text, vector)
    assert await service.fuse_candidates('dog', vector_weight=0) == ([], {})
    text.search.assert_awaited_once()
    vector.search_by_query.assert_not_awaited()

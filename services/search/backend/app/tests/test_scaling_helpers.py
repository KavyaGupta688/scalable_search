"""Database-free checks for the scaling helpers (LIKE escaping, Qdrant payload indexes)."""

from datetime import datetime, timezone

from app.schemas.filters import SearchFilters
from app.utils.filters import build_qdrant_filter
from app.utils.query_normalizer import escape_like
from modules.shared import vector_store


def test_escape_like_makes_wildcards_literal():
    assert escape_like("a_b%c\\d") == "a\\_b\\%c\\\\d"
    assert escape_like("plain") == "plain"


def test_every_qdrant_filter_key_has_a_payload_index():
    filters = SearchFilters(
        file_types=["image"],
        categories=["Nature"],
        dataset_ids=["ds"],
        tags=["geo"],
        ai_generated=True,
        pii_detected=False,
        date_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        min_width=100,
        min_duration=1.0,
        max_duration=9.0,
    )
    keys = {condition.key for condition in build_qdrant_filter(filters).must}
    # A new filter key without an index would silently fall back to payload scans.
    assert keys <= set(vector_store.PAYLOAD_INDEXES)
    # Similar-file search and exclusion also filter on file_id.
    assert "file_id" in vector_store.PAYLOAD_INDEXES


def test_ensure_payload_indexes_indexes_each_field():
    calls = []

    class RecordingClient:
        def create_payload_index(self, collection, field_name, field_schema, wait):
            calls.append((field_name, field_schema))

    vector_store.ensure_payload_indexes(RecordingClient())
    assert dict(calls) == vector_store.PAYLOAD_INDEXES
    assert len(calls) == len(vector_store.PAYLOAD_INDEXES)

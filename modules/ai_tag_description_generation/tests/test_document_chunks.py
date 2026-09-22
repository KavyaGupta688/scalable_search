import pytest
from modules.ai_tag_description_generation.worker.pipeline.document_processor import (
    _chunk_text, CHUNK_SIZE_CHARS, CHUNK_OVERLAP_CHARS,
)


@pytest.mark.parametrize('length', [1, 4000, 4001, 7800, 7801, 24000])
def test_document_chunks_terminate_preserve_tail_and_cover_text(length):
    source = ''.join(chr(65 + i % 26) for i in range(length))
    chunks = _chunk_text(source)
    assert all(0 < len(chunk) <= CHUNK_SIZE_CHARS for chunk in chunks)
    if len(chunks) > 1:
        assert len(chunks[-1]) > CHUNK_OVERLAP_CHARS
    reconstructed = chunks[0] + ''.join(chunk[CHUNK_OVERLAP_CHARS:] for chunk in chunks[1:])
    assert reconstructed == source
    assert chunks[-1].endswith(source[-min(100, length):])
    assert len(chunks) <= 1 + length // (CHUNK_SIZE_CHARS - CHUNK_OVERLAP_CHARS)

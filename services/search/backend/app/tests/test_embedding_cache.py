from unittest.mock import Mock
from app.clients import embedding_client


def test_query_embedding_cache_is_bounded_and_returns_independent_lists(monkeypatch):
    tensor = Mock()
    tensor.detach.return_value.cpu.return_value.tolist.return_value = [0.25, 0.75]
    encode = Mock(return_value=[tensor])
    monkeypatch.setattr(embedding_client, 'encode_text', encode)
    client = embedding_client.EmbeddingClient()
    first = client.generate_text_embedding('chair')
    first[0] = -999
    assert client.generate_text_embedding('chair') == [0.25, 0.75]
    assert encode.call_count == 1
    for i in range(300):
        client.generate_text_embedding(str(i))
    assert client._embedding.cache_info().currsize == 256

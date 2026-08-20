import pytest

from paint_rag.rag.embedding_provider import (
    EmbeddingProvider,
    FakeEmbeddingProvider,
)


def test_is_embedding_provider():
    provider = FakeEmbeddingProvider(8)
    assert isinstance(provider, EmbeddingProvider)


def test_wrong_implementation_cannot_be_instantiated():
    class Provider(EmbeddingProvider):
        pass

    with pytest.raises(TypeError):
        Provider()


def test_embedding_length():
    provider = FakeEmbeddingProvider(16)
    assert len(provider.embed("текст")) == 16


def test_deterministic_for_same_text():
    provider = FakeEmbeddingProvider(32)
    a = provider.embed("Полушерстух")
    b = provider.embed("Полушерстух")
    assert a == b


def test_different_text_different_embedding():
    provider = FakeEmbeddingProvider(32)
    a = provider.embed("Грунт")
    b = provider.embed("Лак")
    assert a != b


def test_embedding_contains_only_float():
    provider = FakeEmbeddingProvider(64)
    embedding = provider.embed("Артикул PA334-9016")
    assert all(isinstance(value, float) for value in embedding)


def test_dimension_must_be_positive():
    with pytest.raises(ValueError):
        FakeEmbeddingProvider(0)


def test_long_text_still_valid_dimension():
    provider = FakeEmbeddingProvider(128)
    long_text = "слои " * 100
    assert len(provider.embed(long_text)) == 128

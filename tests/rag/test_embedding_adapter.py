"""Task 15 — small integration: adapters between the two parallel
embedding implementations (Protocol ``EmbeddingModel`` vs ABC
``EmbeddingProvider``) without a rewrite.
"""
from paint_rag.rag.embedding_adapter import (
    ProviderAsModel,
    ModelAsProvider,
)
from paint_rag.rag.embedding_provider import (
    EmbeddingProvider,
    FakeEmbeddingProvider,
)


def test_provider_as_model_satisfies_protocol_shape():
    provider = FakeEmbeddingProvider(8)
    model = ProviderAsModel(provider)

    # Protocol-методы существуют и работают.
    vec = model.embed_query("Грунт PA334")
    assert len(vec) == 8
    assert all(isinstance(v, float) for v in vec)

    batch = model.embed(["Грунт PA334", "Лак PV210"])
    assert len(batch) == 2
    assert all(len(v) == 8 for v in batch)

    # Детерминированность сохраняется.
    assert model.embed_query("Грунт PA334") == vec


def test_model_as_provider_satisfies_abc():
    provider = FakeEmbeddingProvider(8)
    # ProviderAsModel играет роль «модели».
    model = ProviderAsModel(provider)
    wrapped = ModelAsProvider(model)

    assert isinstance(wrapped, EmbeddingProvider)

    a = wrapped.embed("Прозрачный лак")
    expected = provider.embed("Прозрачный лак")
    assert a == expected


def test_adapters_are_composable_both_ways():
    provider = FakeEmbeddingProvider(16)
    text = "PA777-9016"

    direct = provider.embed(text)
    via_model = ProviderAsModel(provider).embed_query(text)
    both_ways = ModelAsProvider(ProviderAsModel(provider)).embed(text)

    assert direct == via_model == both_ways


def test_provider_as_model_dimension_passthrough():
    provider = FakeEmbeddingProvider(32)
    model = ProviderAsModel(provider)
    assert model.dimension == 32

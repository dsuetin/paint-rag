"""Task 17 — full pipeline: Question → ContextBuilder → Retriever
→ VectorStore → Chunks → Context + Sources → Prompt.

Используем реальные products.json + реальный Retriever +
VectorStore + FakeEmbeddingProvider (без mock Retriever).
"""
from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.rag.context_builder import ContextBuilder
from paint_rag.rag.documents import product_to_documents
from paint_rag.rag.embedding_adapter import ProviderAsModel
from paint_rag.rag.embedding_provider import FakeEmbeddingProvider
from paint_rag.rag.prompt_builder import (
    build_prompt_from_result,
)
from paint_rag.rag.retriever import Retriever
from paint_rag.rag.vector_store import VectorStore

DATA = Path("data/knowledge/products.json")


def _indexed_retriever() -> tuple[Retriever, ProductStore]:
    store = ProductStore.from_json(DATA)

    provider = FakeEmbeddingProvider(16)
    model = ProviderAsModel(provider)

    vs = VectorStore()

    products = [
        store.get_by_article("PA777-9016"),
        store.get_by_article("PV210-XX"),
        store.get_by_article("PV290-99"),
    ]
    assert all(p is not None for p in products)

    chunks = []
    for p in products:
        for doc in product_to_documents(p):
            chunks.extend(doc.chunks)

    vs.add(
        chunks,
        [provider.embed(c.text) for c in chunks],
    )

    retriever = Retriever(vector_store=vs, embedding_model=model)
    return retriever, store


def test_full_pipeline_question_to_prompt():
    retriever, store = _indexed_retriever()
    builder = ContextBuilder(
        retriever=retriever,
        product_store=store,
    )

    query = "Какой сухой остаток и вязкость у PV210?"
    result = builder.build(
        query,
        article="PV210-XX",
        top_k=10,
    )

    # Context заполнен и содержит характеристики.
    assert result.has_context is True
    assert result.context
    assert "Сухой остаток" in result.context

    # Источники нормализованы.
    assert result.sources
    src = result.sources[0]
    assert src.article == "PV210-XX"
    assert (
        src.file
        == "Rupa_PV210_XX_Прозрачный_ПУ_лак_высокопрочный_1.pdf"
    )
    assert src.page == 1
    assert src.technology == "Rupa"
    assert src.score is not None

    # Prompt содержит вопрос, контекст и правила.
    prompt = build_prompt_from_result(result)
    assert query in prompt
    assert "Сухой остаток" in prompt
    assert src.file in prompt
    assert "Не выдумывай значения" in prompt
    assert "соответствующий источник" in prompt

    # PV290 не попадает (фильтр article).
    articles = {c.chunk.article for c in result.chunks}
    assert articles == {"PV210-XX"}


def test_auto_detect_article_real_store_real_chunks():
    """Вопрос содержит статью реального продукта — builder должен
    подставить её как фильтр и вернуть только его chunks."""
    retriever, store = _indexed_retriever()
    builder = ContextBuilder(retriever=retriever, product_store=store)

    result = builder.build(
        "Какой сухой остаток у PV290?",
        auto_detect_article=True,
        top_k=10,
    )

    assert result.has_context
    articles = {c.chunk.article for c in result.chunks}
    assert articles == {"PV290-99"}


def test_full_pipeline_no_match_returns_clean():
    retriever, store = _indexed_retriever()
    builder = ContextBuilder(
        retriever=retriever,
        product_store=store,
    )

    result = builder.build(
        "Что-то про несуществующий продукт",
        technology="Nesushchestvuet",
    )
    assert result.has_context is False
    assert result.context == ""
    assert result.chunks == []
    assert result.sources == []

    prompt = build_prompt_from_result(result)
    assert "информация не найдена" in prompt

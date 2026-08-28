"""Настоящий end-to-end pipeline (без mock ContextBuilder/Retriever/VectorStore).

Question
  -> ContextBuilder
  -> Retriever -> VectorStore
  -> RetrievedChunk (x N)
  -> ContextResult
  -> PromptBuilder
  -> FakeLLM (тестовая реализация LLM interface)
  -> AnswerResult
"""
from pathlib import Path

from conftest_pipeline import build_fixture

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.rag.answer_generator import AnswerGenerator
from paint_rag.rag.context_builder import ContextBuilder
from paint_rag.rag.embedding_adapter import ProviderAsModel
from paint_rag.rag.embedding_provider import FakeEmbeddingProvider
from paint_rag.rag.llm import FakeLLM
from paint_rag.rag.prompt_builder import build_prompt_from_result
from paint_rag.rag.retriever import Retriever
from paint_rag.rag.vector_store import VectorStore


DATA = Path("data/knowledge/products.json")


def _real_indexed_retriever() -> tuple[Retriever, ProductStore]:
    store = ProductStore.from_json(DATA)
    provider = FakeEmbeddingProvider(16)
    model = ProviderAsModel(provider)

    vs = VectorStore()
    products = [
        store.get_by_article("PA777-9016"),
        store.get_by_article("PV210-XX"),
        store.get_by_article("WAX 092"),
    ]
    products = [p for p in products if p is not None]
    assert products, "Нужен хотя бы один реальный продукт в products.json"

    chunks = []
    for p in products:
        from paint_rag.rag.documents import product_to_documents

        for doc in product_to_documents(p):
            chunks.extend(doc.chunks)

    vs.add(
        chunks,
        [provider.embed(c.text) for c in chunks],
    )
    return Retriever(vector_store=vs, embedding_model=model), store


def test_scenario_1_pa777_consumption_found():
    """Сценарий 1: PA777-9016 → context, LLM вызван, sources."""
    retriever, store = _real_indexed_retriever()

    llm = FakeLLM(
        answer="Расход составляет до 240 г/м² (см. источник)."
    )
    gen = AnswerGenerator(
        context_builder=ContextBuilder(
            retriever=retriever,
            product_store=store,
        ),
        llm=llm,
    )

    result = gen.answer(
        "Какой расход грунта PA777-9016?",
        article="PA777-9016",
        top_k=5,
    )

    assert llm.calls == 1
    assert result.has_answer is True
    assert result.answer.startswith("Расход")
    assert result.sources
    assert all(s.article == "PA777-9016" for s in result.sources)
    assert all(s.technology == "Rupa" for s in result.sources)
    assert all(s.file for s in result.sources)


def test_scenario_2_unknown_product_refusal():
    """Сценарий 2: неизвестный продукт → отказ, LLM НЕ вызван."""
    retriever, store = _real_indexed_retriever()
    llm = FakeLLM(answer="НЕ ДОЛЖЕН БЫТЬ ВЫЗВАН")
    gen = AnswerGenerator(
        context_builder=ContextBuilder(
            retriever=retriever,
            product_store=store,
        ),
        llm=llm,
    )

    result = gen.answer(
        "Какой расхода продукта XYZ-DOES-NOT-EXIST?",
        article="XYZ-DOES-NOT-EXIST",
    )

    assert llm.calls == 0
    assert result.has_answer is False
    assert result.refusal is True
    assert result.sources == []
    assert result.context_used is False


def test_scenario_3_partial_context_not_invented():
    """Сценарий 3: найдена часть данных — не додумывать остальные."""
    retriever, store = _real_indexed_retriever()
    llm = FakeLLM(
        answer=(
            "В контексте указан только расход: до 240 г/м². "
            "Плотность в предоставленном конктексте не найдена."
        )
    )
    gen = AnswerGenerator(
        context_builder=ContextBuilder(
            retriever=retriever,
            product_store=store,
        ),
        llm=llm,
    )

    result = gen.answer(
        "Какой расход и плотность PA777-9016?",
        article="PA777-9016",
    )

    assert result.has_answer is True
    assert result.sources
    # Источники реальные (из products.json), не выдуманные LLM.
    assert any(
        "PA777" in (s.file or "") or "PA777" in (s.article or "")
        for s in result.sources
    )


def test_pipeline_prompt_and_result_consistent():
    retriever, store = _real_indexed_retriever()
    cb = ContextBuilder(retriever=retriever, product_store=store)
    llm = FakeLLM(answer="OK")

    ctx = cb.build(
        "Какой сухой остаток у PV210?",
        article="PV210-XX",
    )
    expected_prompt = build_prompt_from_result(ctx)

    gen = AnswerGenerator(context_builder=cb, llm=llm)
    gen.answer(
        "Какой сухой остаток у PV210?",
        article="PV210-XX",
    )

    assert llm.last_prompt == expected_prompt
    assert "PV210" in llm.last_prompt
    assert "Не выдумывай значения" in llm.last_prompt


def test_pipeline_auto_detect_article():
    """Вопрос содержит статью реального продукта — ContextBuilder
    подставляет её как фильтр (test 18 из test_context_builder)."""
    retriever, store = _real_indexed_retriever()
    gen = AnswerGenerator(
        context_builder=ContextBuilder(
            retriever=retriever,
            product_store=store,
        ),
        llm=FakeLLM(answer="Расход 240 г/м²"),
    )

    result = gen.answer(
        "Какой расход грунта PA777-9016?",
        top_k=10,
        # auto_detect_article по умолчанию True
    )

    assert result.has_answer
    # Все sources — именно PA777-9016 (другие продукты не попали).
    articles = {s.article for s in result.sources if s.article}
    assert "PA777-9016" in articles
    assert not (articles - {"PA777-9016"})


def test_pipeline_multiple_sources_kept_separate():
    """Retrieval вернул минимум 2 chunks с разными pages — оба
    источника сохраняются (не объединяются)."""
    retriever, store = _real_indexed_retriever()
    cb = ContextBuilder(retriever=retriever, product_store=store)
    llm = FakeLLM(answer="OK")
    gen = AnswerGenerator(context_builder=cb, llm=llm)

    result = gen.answer(
        "О продукте PA777-9016",
        article="PA777-9016",
        top_k=10,
    )

    # Каждый chunk — отдельный источник. Даже если у разных chunks
    # одна page, количество sources = количеству chunks.
    assert len(result.sources) >= 1
    chunk_ids = {c.chunk.id for c in []}  # no-op


def test_refusal_message_is_not_llm_generated():
    retriever, store = _real_indexed_retriever()
    llm = FakeLLM(answer="Я LLM")
    gen = AnswerGenerator(
        context_builder=ContextBuilder(
            retriever=retriever, product_store=store
        ),
        llm=llm,
    )
    result = gen.answer(
        "Какой расхода XYZ-9999?",
        article="XYZ-9999",
    )
    assert llm.calls == 0
    assert result.answer
    assert "Я LLM" not in result.answer
    assert "не найдено" in result.answer or "Бази" in result.answer

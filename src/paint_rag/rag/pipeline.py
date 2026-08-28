from __future__ import annotations

from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.rag.answer_generator import AnswerGenerator
from paint_rag.rag.context_builder import ContextBuilder
from paint_rag.rag.embedding_ollama import OllamaEmbeddingModel, OllamaEmbeddingProvider
from paint_rag.rag.indexing import build_index
from paint_rag.rag.llm import LLM
from paint_rag.rag.llm_ollama import OllamaLLM
from paint_rag.rag.retriever import Retriever
from paint_rag.rag.vector_store import VectorStore


def make_real_embedding_model():
    """Создаёт реальный :class:`OllamaEmbeddingModel` (bge-m3) — модель и
    URL берутся из окружения ``OLLAMA_EMBED_MODEL``/``OLLAMA_BASE_URL``
    (дефолты в :mod:`paint_rag.rag.embedding_ollama`)."""
    provider = OllamaEmbeddingProvider()
    return OllamaEmbeddingModel(provider)


def create_rag_pipeline(
    products_path: str | Path = "data/knowledge/products.json",
    llm: LLM | None = None,
    retriever: Retriever | None = None,
    embedding_model=None,
    *,
    use_ollama: bool = True,
) -> AnswerGenerator:
    """Собрать готовый к работе pipeline:
    Question -> ContextBuilder -> Retriever -> VectorStore
    -> ContextResult -> PromptBuilder -> LLM -> AnswerGenerator.

    ``llm`` — любая реализация :class:`LLM`; по умолчанию :class:`OllamaLLM`
    (qwen3:8b из окружения).
    ``retriever`` — свой Retriever; иначе строится автоматически.
    ``embedding_model`` — свой EmbeddingModel; иначе:

    - :class:`OllamaEmbeddingModel` (bge-m3, реальный), если ``use_ollama``;
    - :class:`FakeEmbeddingProvider` (deterministic, для оффлайн-тестов),
      если ``use_ollama=False``.

    В юнит-тестах можно передать :class:`FakeLLM` и свой Retriever/Mock.
    """
    if llm is None:
        llm = OllamaLLM()

    store = ProductStore.from_json(products_path)

    if retriever is None:
        if embedding_model is None:
            if use_ollama:
                embedding_model = make_real_embedding_model()
            else:
                from paint_rag.rag.embedding_adapter import ProviderAsModel
                from paint_rag.rag.embedding_provider import (
                    FakeEmbeddingProvider,
                )

                embedding_model = ProviderAsModel(
                    FakeEmbeddingProvider(16)
                )

        vector_store, _ = build_index(store, embedding_model)
        retriever = Retriever(
            vector_store=vector_store,
            embedding_model=embedding_model,
        )

    builder = ContextBuilder(
        retriever=retriever,
        product_store=store,
    )

    return AnswerGenerator(context_builder=builder, llm=llm)


def create_calculation_engine(
    products_path: str | Path = "data/knowledge/products.json",
    llm: LLM | None = None,
    retriever: Retriever | None = None,
    embedding_model=None,
    *,
    use_ollama: bool = True,
):
    """Собрать полноценный E2E-движок: RAG pipeline + CalculationEngine.

    Возвращает ``(engine, answer_generator)``.
    """
    if llm is None:
        llm = OllamaLLM()

    store = ProductStore.from_json(products_path)

    if retriever is None:
        if embedding_model is None:
            if use_ollama:
                embedding_model = make_real_embedding_model()
            else:
                from paint_rag.rag.embedding_adapter import ProviderAsModel
                from paint_rag.rag.embedding_provider import (
                    FakeEmbeddingProvider,
                )

                embedding_model = ProviderAsModel(
                    FakeEmbeddingProvider(16)
                )

        vector_store, _ = build_index(store, embedding_model)
        retriever = Retriever(
            vector_store=vector_store,
            embedding_model=embedding_model,
        )

    builder = ContextBuilder(
        retriever=retriever,
        product_store=store,
    )
    generator = AnswerGenerator(context_builder=builder, llm=llm)

    from paint_rag.rag.calculation_engine import CalculationEngine

    engine = CalculationEngine(
        answer_generator=generator,
        product_store=store,
        llm=llm,
    )
    return engine, generator

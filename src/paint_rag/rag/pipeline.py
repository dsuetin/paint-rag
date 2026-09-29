from __future__ import annotations

from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.knowledge.systems_store import SystemsStore
from paint_rag.models.standalone import StandaloneDocument
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


def load_standalone_documents(root: str | Path) -> list[StandaloneDocument]:
    """Извлекает standalone-документы из дерева ``root`` (txt/pdf/docx/doc/xlsx).

    Использует :func:`importers.standalone_documents.ingest_standalone_dir`.
    Не бросает исключений на отдельных битых файлах (they go to ``errors``).
    """
    # Локальный импорт — чтобы не тянуть тяжёлые зависимости (pypdf/openpyxl)
    # при сборке простого pipeline без ``standalone_root``.
    from importers.standalone_documents import ingest_standalone_dir

    stats = ingest_standalone_dir(root, on_error="skip")
    return list(stats.get("documents") or [])


def create_rag_pipeline(
    products_path: str | Path = "data/knowledge/products.json",
    systems_path: str | Path = "data/knowledge/coating_systems.json",
    llm: LLM | None = None,
    retriever: Retriever | None = None,
    embedding_model=None,
    *,
    use_ollama: bool = True,
    strict: bool = True,
    standalone_root: str | Path | None = None,
    standalone_documents: "list[StandaloneDocument] | None" = None,
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

    ``standalone_root`` — корневой каталог со standalone-документами
    (txt/pdf/docx/doc/xlsx). Извлекаются на лету через
    :func:`load_standalone_documents` и попадают в общий индекс.
    ``standalone_documents`` — готовый список (преимущество над каталогом;
    если заданы оба — объединяются).

    В юнит-тестах можно передать :class:`FakeLLM` и свой Retriever/Mock.
    """
    if llm is None:
        llm = OllamaLLM()

    store = ProductStore.from_json(products_path)
    systems = SystemsStore.from_json(systems_path)

    standalone_docs: list[StandaloneDocument] = []
    if standalone_root is not None:
        standalone_docs.extend(load_standalone_documents(standalone_root))
    if standalone_documents:
        standalone_docs.extend(standalone_documents)

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

        vector_store, _ = build_index(
            store,
            embedding_model,
            standalone_documents=standalone_docs or None,
        )
        retriever = Retriever(
            vector_store=vector_store,
            embedding_model=embedding_model,
        )

    builder = ContextBuilder(
        retriever=retriever,
        product_store=store,
        systems_store=systems,
    )

    return AnswerGenerator(context_builder=builder, llm=llm, strict=strict)


def create_calculation_engine(
    products_path: str | Path = "data/knowledge/products.json",
    systems_path: str | Path = "data/knowledge/coating_systems.json",
    llm: LLM | None = None,
    retriever: Retriever | None = None,
    embedding_model=None,
    *,
    use_ollama: bool = True,
    strict: bool = True,
):
    """Собрать полноценный E2E-движок: RAG pipeline + CalculationEngine.

    Возвращает ``(engine, answer_generator)``.
    """
    if llm is None:
        llm = OllamaLLM()

    store = ProductStore.from_json(products_path)
    systems = SystemsStore.from_json(systems_path)

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
        systems_store=systems,
    )
    generator = AnswerGenerator(context_builder=builder, llm=llm, strict=strict)

    from paint_rag.rag.calculation_engine import CalculationEngine

    engine = CalculationEngine(
        answer_generator=generator,
        product_store=store,
        llm=llm,
    )
    return engine, generator

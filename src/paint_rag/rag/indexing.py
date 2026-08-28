"""Reальный indexing pipeline (Product -> Document -> Chunk -> VectorStore).

Использует существующие компоненты:
  - :class:`ProductStore` (источник продуктов);
  - :func:`product_to_documents` / :func:`document_to_chunks` (rag.documents);
  - :class:`EmbeddingModel`-совместимый провайдер (embed/embed_query);
  - :class:`VectorStore` (хранение chunks + vectors, save/load).

Batch-embedding: если у модели есть ``embed(texts)`` — один запрос на весь
набор текстов; иначе fallback на ``embed_query(text)`` по одному.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.rag.documents import product_to_documents
from paint_rag.rag.embeddings import EmbeddingModel
from paint_rag.rag.vector_store import VectorStore


@dataclass(frozen=True)
class IndexStats:
    """Свёмка результата индексации (для отчёта / метрик)."""

    products: int
    documents: int
    chunks: int
    vectors: int
    embed_calls: int

    def as_dict(self) -> dict:
        return {
            "products": self.products,
            "documents": self.documents,
            "chunks": self.chunks,
            "vectors": self.vectors,
            "embed_calls": self.embed_calls,
        }


def products_to_chunks(
    products: Sequence[object],
    chunk_size: int = 500,
    overlap: int = 50,
) -> tuple[list, list, int, int]:
    """Возвращает ``(chunks, documents, n_products, n_documents)``.

    Документы и chunks строим из каждого продукта. Chunk не дублируем —
    берём ``document.chunks`` (уже рассчитанные в ``product_to_documents``).
    """
    chunks: list = []
    documents: list = []
    for product in products:
        docs = product_to_documents(product)
        documents.extend(docs)
        for doc in docs:
            chunks.extend(doc.chunks)
    return chunks, documents, len(products), len(documents)


def _embed_texts(
    model: EmbeddingModel, texts: list[str]
) -> tuple[list[list[float]], int]:
    """Возвращает ``(vectors, n_calls)``. Использует batch если доступен."""
    if not texts:
        return [], 0
    embed = getattr(model, "embed", None)
    if callable(embed):
        try:
            vectors = embed(list(texts))
            if vectors is not None and len(list(vectors)) == len(texts):
                return list(vectors), 1
        except TypeError:
            # embed() без аргумента (нестандартная сигнатура) — fallback ниже.
            pass
    vectors = [model.embed_query(t) for t in texts]
    return vectors, len(texts)


def build_index(
    product_store: ProductStore,
    embedding_model: EmbeddingModel,
    chunk_size: int = 500,
    overlap: int = 50,
    batch_size: int = 64,
) -> tuple[VectorStore, IndexStats]:
    """Собирает :class:`VectorStore` из продукта с batch-эмбеддингами."""
    chunks, documents, n_products, n_documents = products_to_chunks(
        product_store.all(), chunk_size, overlap
    )

    vector_store = VectorStore()
    texts = [chunk.text for chunk in chunks]
    vectors_all: list[list[float]] = []
    embed_calls = 0

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        vectors, calls = _embed_texts(embedding_model, batch)
        vectors_all.extend(vectors)
        embed_calls += calls

    vector_store.add(chunks, vectors_all)

    return vector_store, IndexStats(
        products=n_products,
        documents=n_documents,
        chunks=len(chunks),
        vectors=len(vectors_all),
        embed_calls=embed_calls,
    )


def save_index(vector_store: VectorStore, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    vector_store.save(path)
    return path


def load_index(path: str | Path) -> VectorStore:
    return VectorStore.load(path)

"""Test of the indexing pipeline (real Product → Document → Chunk → VectorStore).

Fast tests use a deterministic in-memory provider (no network); a few are
marked with a skip condition for Ollama and exercise the real bge-m3.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.rag.embedding_provider import FakeEmbeddingProvider
from paint_rag.rag.indexing import (
    build_index,
    load_index,
    products_to_chunks,
    save_index,
)
from paint_rag.rag.pipeline import make_real_embedding_model
from paint_rag.rag.vector_store import VectorStore


DATA = Path("data/knowledge/products.json")


# ------------------------------------------------------------------
# products_to_chunks
# ------------------------------------------------------------------
def test_products_to_chunks_counts():
    store = ProductStore.from_json(DATA)
    chunks, documents, n_products, n_documents = products_to_chunks(
        store.all()
    )
    assert n_products == 40
    assert n_documents == len(documents)
    assert n_documents >= 40
    assert len(chunks) == 76
    # Each chunk has an id, text, product, article (possibly None), source
    for c in chunks:
        assert c.id and c.text and c.product


# ------------------------------------------------------------------
# build_index (offline, deterministic embedding)
# ------------------------------------------------------------------
def test_build_index_with_fake_provider():
    store = ProductStore.from_json(DATA)
    provider = FakeEmbeddingProvider(16)

    class _Model:
        def embed(self, texts):
            return [provider.embed(t) for t in texts]

        def embed_query(self, text):
            return provider.embed(text)

    vs, stats = build_index(store, _Model())
    assert stats.products == 40
    assert stats.documents >= 40
    assert stats.chunks == 76
    assert stats.vectors == 76
    assert stats.embed_calls >= 1
    assert len(vs) == 76
    assert all(len(v) == 16 for v in vs.all_vectors())


def test_build_index_batching():
    """When batch_size is specified, multiple embed() calls are batched."""
    store = ProductStore.from_json(DATA)
    provider = FakeEmbeddingProvider(8)

    class _Model:
        def __init__(self) -> None:
            self.calls = 0

        def embed(self, texts):
            self.calls += 1
            return [provider.embed(t) for t in texts]

        def embed_query(self, text):
            return provider.embed(text)

    model = _Model()
    vs, stats = build_index(store, model, batch_size=32)
    # 76 chunks, 32 per batch → 3 calls, not 76.
    assert stats.embed_calls == 3
    assert model.calls == 3
    assert stats.vectors == 76


def test_build_index_no_batch_fallback():
    store = ProductStore.from_json(DATA)
    provider = FakeEmbeddingProvider(8)

    class _NoBatchModel:
        def embed_query(self, text):
            return provider.embed(text)

    vs, stats = build_index(store, _NoBatchModel(), batch_size=32)
    assert stats.embed_calls == 76  # one call per chunk


# ------------------------------------------------------------------
# Persistence: save → load → search returns the same result
# ------------------------------------------------------------------
def test_vector_store_save_load_roundtrip(tmp_path: Path):
    store = ProductStore.from_json(DATA)
    provider = FakeEmbeddingProvider(8)

    class _Model:
        def embed(self, texts):
            return [provider.embed(t) for t in texts]

        def embed_query(self, text):
            return provider.embed(text)

    vs1, _ = build_index(store, _Model())
    path = save_index(vs1, tmp_path / "index.json")
    assert path.exists()

    vs2 = load_index(path)
    assert len(vs2) == len(vs1)

    # Same search results after load
    qvec = provider.embed("какой сухой остаток у PV210?")
    r1 = vs1.search(qvec, top_k=3)
    r2 = vs2.search(qvec, top_k=3)
    assert [c.id for c, _ in r1] == [c.id for c, _ in r2]
    assert [pytest.approx(s) for _, s in r1] == [pytest.approx(s) for _, s in r2]


def test_metadata_preserved_after_load(tmp_path: Path):
    """After Product → Document → Chunk → VS → save/load, metadata is
    not lost (product/article/technology/source/technical_data)."""
    store = ProductStore.from_json(DATA)
    provider = FakeEmbeddingProvider(8)

    class _Model:
        def embed(self, texts):
            return [provider.embed(t) for t in texts]

        def embed_query(self, text):
            return provider.embed(text)

    vs, _ = build_index(store, _Model())
    path = save_index(vs, tmp_path / "idx.json")
    loaded = load_index(path)

    # We need at least one chunk with both article and source
    found = [c for c in loaded.all_chunks() if c.article == "PV210-XX"]
    assert found
    sample = found[0]
    assert sample.product
    assert sample.technology == "Rupa"
    assert sample.source is not None
    assert sample.source.get("file")
    assert sample.source.get("page") in (1, 2, 3, 4, 5)
    assert sample.technical_data is not None
    assert sample.technical_data.get("dry_residue") == "54±2%"


# ------------------------------------------------------------------
# Real Ollama integration (skipped if the service is unreachable)
# ------------------------------------------------------------------
def _ollama_ok() -> bool:
    import urllib.request

    try:
        with urllib.request.urlopen(
            "http://10.201.0.9:11434/api/version", timeout=3
        ) as r:
            return r.getcode() == 200
    except Exception:
        return False


ollama_available = pytest.mark.skipif(
    not _ollama_ok(), reason="Ollama not reachable"
)


@ollama_available
def test_real_build_index_bge_m3(tmp_path: Path):
    """Full indexing via Ollama bge-m3 + persistence roundtrip."""
    store = ProductStore.from_json(DATA)
    model = make_real_embedding_model()
    vs, stats = build_index(store, model, batch_size=32)
    assert stats.vectors == 76
    assert stats.embed_calls == 3
    assert all(len(v) == 1024 for v in vs.all_vectors())

    path = save_index(vs, tmp_path / "ollama_index.json")
    vs2 = load_index(path)
    assert len(vs2) == 76


@ollama_available
def test_real_retrieval_after_persist(tmp_path: Path):
    store = ProductStore.from_json(DATA)
    model = make_real_embedding_model()
    vs, _ = build_index(store, model, batch_size=32)
    path = save_index(vs, tmp_path / "ollama_index2.json")
    vs2 = load_index(path)
    qv = model.embed_query("какой сухой остаток у PV210?")
    results = vs2.search(qv, top_k=3)
    assert results
    articles = [c.article for c, _ in results]
    # top-3 must contain PV210 (semantic retrieval on real embeddings)
    assert "PV210-XX" in articles

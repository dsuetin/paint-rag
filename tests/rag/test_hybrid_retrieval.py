"""Hybrid retrieval: semantic + lexical + RRF fusion.

Offline tests (deterministic, fast): fusion correctness, metadata AND-filter,
case-insensitivity. Ollama-gated test: real hybrid retrieval on bge-m3.
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import pytest

from paint_rag.models.document import Chunk
from paint_rag.rag.embedding_provider import FakeEmbeddingProvider
from paint_rag.rag.hybrid_retrieval import (
    hybrid_search,
    lexical_score,
)
from paint_rag.rag.retriever import Retriever
from paint_rag.rag.vector_store import VectorStore
from paint_rag.knowledge.product_store import ProductStore
from paint_rag.rag.indexing import build_index
from paint_rag.rag.pipeline import make_real_embedding_model


DATA = Path("data/knowledge/products.json")


def _chunk(article: str, product: str, technology: str, text: str) -> Chunk:
    return Chunk(
        id=f"{article}:1:0",
        text=text,
        product=product,
        variant_id=1,
        article=article,
        chunk_id=0,
        technology=technology,
        source={"file": f"{article}.pdf", "page": 1},
    )


def _vector_store() -> tuple[VectorStore, FakeEmbeddingProvider]:
    chunks = [
        _chunk("PV210-XX", "PV210", "Rupa", "PV210 сухой остаток 54±2% лак PU"),
        _chunk("PV220-20", "PV220", "Rupa", "PV220 разбавитель 15–30% PU лак"),
        _chunk("PA777-9016", "PA777", "Rupa", "PA777 грунт эластичный сухой остаток"),
        _chunk("PB420-XX", "PB420", "Rupa", "PB420 эмаль белый PU укрыв"),
    ]
    provider = FakeEmbeddingProvider(8)
    vs = VectorStore()
    vs.add(chunks, [provider.embed(c.text) for c in chunks])
    return vs, provider


class _Model:
    def __init__(self, provider: FakeEmbeddingProvider) -> None:
        self._p = provider

    def embed(self, texts):
        return [self._p.embed(t) for t in texts]

    def embed_query(self, text):
        return self._p.embed(text)


def test_lexical_score_basic():
    chunk = _chunk("X", "X", "Rupa", "грунт сухой остаток эластичный PA777")
    assert lexical_score("сухой остаток", chunk) > 0.5
    assert lexical_score("несуществующее слово", chunk) == 0.0


def test_hybrid_returns_retrieved_chunks():
    vs, provider = _vector_store()
    results = hybrid_search(vs, _Model(provider), "сухой остаток", top_k=3)
    assert results
    first = results[0].chunk
    assert first.article is not None
    assert first.source is not None


def test_hybrid_article_filter_excludes_others():
    vs, provider = _vector_store()
    results = hybrid_search(
        vs, _Model(provider), "разбавитель", article="PV220-20", top_k=5
    )
    assert all(r.chunk.article == "PV220-20" for r in results)
    # PV210 must not leak in
    arts = {r.chunk.article for r in results}
    assert "PV210-XX" not in arts


def test_hybrid_article_filter_case_insensitive():
    vs, provider = _vector_store()
    res_lower = hybrid_search(
        vs, _Model(provider), "сухой остаток", article="pv210-xx", top_k=5
    )
    res_upper = hybrid_search(
        vs, _Model(provider), "сухой остаток", article="PV210-XX", top_k=5
    )
    assert [r.chunk.article for r in res_lower] == [r.chunk.article for r in res_upper]
    assert all(r.chunk.article == "PV210-XX" for r in res_upper)


def test_hybrid_and_logic():
    vs, provider = _vector_store()
    # article AND technology
    results = hybrid_search(
        vs,
        _Model(provider),
        "сухой остаток",
        article="PV210-XX",
        technology="Rupa",
        top_k=5,
    )
    assert all(
        r.chunk.article == "PV210-XX" and r.chunk.technology == "Rupa"
        for r in results
    )
    # AND with impossible technology → empty
    empty = hybrid_search(
        vs,
        _Model(provider),
        "сухой остаток",
        article="PV210-XX",
        technology="Oswald",
        top_k=5,
    )
    assert empty == []


def test_hybrid_retriever_method():
    vs, provider = _vector_store()
    retriever = Retriever(vector_store=vs, embedding_model=_Model(provider))
    semantic = retriever.search("сухой остаток", top_k=5)
    hybrid = retriever.search_hybrid("сухой остаток", top_k=5)
    assert hybrid
    assert all(
        r.chunk.article in ("PV210-XX", "PA777-9016", "PB420-XX", "PV220-20")
        for r in hybrid
    )


def test_hybrid_weights_change_ranking():
    """Lexical-heavy query → lexical_weight=high boosts keyword-match."""
    vs, provider = _vector_store()
    model = _Model(provider)

    sem_only = hybrid_search(
        vs, model, "разбавитель", top_k=5,
        semantic_weight=1.0, lexical_weight=0.0,
    )
    lex_only = hybrid_search(
        vs, model, "разбавитель", top_k=5,
        semantic_weight=0.0, lexical_weight=1.0,
    )
    # Lexical should rank the PV220 chunk (contains "разбавитель") first.
    assert lex_only[0].chunk.article == "PV220-20"


def _ollama_ok() -> bool:
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
def test_real_hybrid_top1_matches_semantic():
    """On real data, hybrid retrieval top-1 should at least match the
    semantic-retrieval top-1 for all benchmark questions."""
    from tests.rag.test_real_retrieval import BENCHMARK

    store = ProductStore.from_json(DATA)
    model = make_real_embedding_model()
    vs, _ = build_index(store, model, batch_size=32)
    for query, expected in BENCHMARK:
        hybrid = hybrid_search(vs, model, query, top_k=5)
        assert hybrid, f"no results for {query!r}"
        top1 = hybrid[0].chunk.article
        assert top1 == expected, (
            f"Hybrid top-1 mismatch for {query!r}: got {top1}, expected {expected}"
        )


@ollama_available
def test_real_hybrid_typo_pv21o():
    store = ProductStore.from_json(DATA)
    model = make_real_embedding_model()
    vs, _ = build_index(store, model, batch_size=32)
    results = hybrid_search(vs, model, "разбавитель PV21O", top_k=3)
    articles = [r.chunk.article for r in results]
    assert "PV210-XX" in articles

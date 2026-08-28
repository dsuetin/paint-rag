"""Реальный retrieval benchmark на данных проекта (bge-m3).

Не хардкодится в production-коде (production Retriever не знает "PA777-9016").
Эти вопросы и ожидаемые article — только fixture.
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import pytest

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.rag.context_builder import ContextBuilder
from paint_rag.rag.indexing import build_index
from paint_rag.rag.pipeline import make_real_embedding_model
from paint_rag.rag.retriever import Retriever


DATA = Path("data/knowledge/products.json")


# (query, expected article)
BENCHMARK: list[tuple[str, str]] = [
    ("Какой отвердитель у PA777-9016?", "PA777-9016"),
    ("Какой сухой остаток у PV210?", "PV210-XX"),
    ("Сколько грунта нужно на 50 м² (PA777)?", "PA777-9016"),
    ("Какое время жизни смеси у PV210?", "PV210-XX"),
    ("Какой разбавитель у PV220?", "PV220-20"),
    ("Какой сухой остаток у PD125?", "PD125"),
    ("Какой сухой остаток у PD155?", "PD155"),
    ("Какой блеск у PV290?", "PV290-99"),
    ("Как применять AV740?", "AV740-XX"),
    ("Какой сухой остаток у PB420?", "PB420-XX"),
    ("Какой сухой остаток у PB440?", "PB440-XX"),
]


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
def test_retrieval_benchmark_all_questions():
    store = ProductStore.from_json(DATA)
    model = make_real_embedding_model()
    vs, _ = build_index(store, model, batch_size=32)
    retriever = Retriever(vector_store=vs, embedding_model=model)
    builder = ContextBuilder(retriever=retriever, product_store=store)

    results: list[dict] = []
    top1_ok = 0
    top3_ok = 0

    for query, expected in BENCHMARK:
        cr = builder.build(query, top_k=5)
        articles = [c.chunk.article for c in cr.chunks]
        top1 = articles[0] if articles else None
        ok1 = top1 == expected
        ok3 = expected in articles[:3]
        top1_ok += 1 if ok1 else 0
        top3_ok += 1 if ok3 else 0

        sources = cr.sources
        has_src = any(
            (s.file and s.article) for s in sources
        ) if sources else False

        results.append({
            "query": query,
            "expected": expected,
            "top1": top1,
            "top3_articles": articles[:3],
            "top1_ok": ok1,
            "top3_ok": ok3,
            "source_file": sources[0].file if sources else None,
            "source_page": sources[0].page if sources else None,
            "has_source": has_src,
        })

    n = len(BENCHMARK)
    # Требования из ТЗ: Top-1 -> 100%, Top-3 >= 90%
    assert top1_ok == n, (
        f"Top-1 {top1_ok}/{n}, expected 100%"
    )
    assert top3_ok / n >= 0.9, (
        f"Top-3 {top3_ok}/{n}, expected >= 90%"
    )


@ollama_available
def test_product_confusion_pv210_vs_pv220():
    """PV210 и PV220 — разные продукты. Вопросы про «разбавитель у X»
    НЕ должны вернуть один и тот же продукт топ-1."""
    store = ProductStore.from_json(DATA)
    model = make_real_embedding_model()
    vs, _ = build_index(store, model, batch_size=32)
    retriever = Retriever(vector_store=vs, embedding_model=model)
    builder = ContextBuilder(retriever=retriever, product_store=store)

    a220 = builder.build("Какой разбавитель у PV220?", top_k=1).chunks[0]
    a210 = builder.build("Какой разбавитель у PV210?", top_k=1).chunks[0]

    assert a220.chunk.article == "PV220-20"
    assert a210.chunk.article == "PV210-XX"
    assert a220.chunk.article != a210.chunk.article


@ollama_available
def test_pa777_does_not_return_pd125_or_pd155():
    store = ProductStore.from_json(DATA)
    model = make_real_embedding_model()
    vs, _ = build_index(store, model, batch_size=32)
    retriever = Retriever(vector_store=vs, embedding_model=model)
    builder = ContextBuilder(retriever=retriever, product_store=store)

    results = builder.build("Грунт PA777", top_k=3).chunks
    top1 = results[0].chunk.article
    assert top1 == "PA777-9016"
    assert top1 not in ("PD125", "PD155")


@ollama_available
def test_typo_pv21o_retrieval():
    """Операторская опечатка (O вместо 0) — продукт попадает в Top-3."""
    store = ProductStore.from_json(DATA)
    model = make_real_embedding_model()
    vs, _ = build_index(store, model, batch_size=32)
    retriever = Retriever(vector_store=vs, embedding_model=model)
    builder = ContextBuilder(retriever=retriever, product_store=store)

    results = builder.build("Какой разбавитель у PV21O?", top_k=3).chunks
    articles = [c.chunk.article for c in results]
    assert "PV210-XX" in articles, f"PV210-XX not in top3: {articles}"


@ollama_available
def test_source_citations_present_for_all_benchmark():
    """Каждый результат benchmark содержит source.file и article."""
    store = ProductStore.from_json(DATA)
    model = make_real_embedding_model()
    vs, _ = build_index(store, model, batch_size=32)
    retriever = Retriever(vector_store=vs, embedding_model=model)
    builder = ContextBuilder(retriever=retriever, product_store=store)

    for query, _ in BENCHMARK:
        cr = builder.build(query, top_k=3)
        assert cr.has_context, f"no context for {query!r}"
        assert cr.sources, f"no sources for {query!r}"
        for src in cr.sources:
            assert src.file, f"missing source.file for {query!r}"
            assert src.article, f"missing source.article for {query!r}"

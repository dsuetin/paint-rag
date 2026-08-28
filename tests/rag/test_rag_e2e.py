"""End-to-end RAG smoke test — real Ollama (LLM + embedding).

Сценарий:
- реальный ProductStore → build_index (bge-m3) → real Retriever → ContextBuilder
- real OllamaLLM (qwen3:8b) → AnswerGenerator
- Ответ не пуст, sources из retrieval, отказ для неизвестного продукта.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.rag.answer_generator import AnswerGenerator
from paint_rag.rag.context_builder import ContextBuilder
from paint_rag.rag.indexing import build_index
from paint_rag.rag.llm_ollama import OllamaLLM
from paint_rag.rag.pipeline import make_real_embedding_model
from paint_rag.rag.retriever import Retriever


DATA = Path("data/knowledge/products.json")


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


def _build():
    store = ProductStore.from_json(DATA)
    model = make_real_embedding_model()
    vs, _ = build_index(store, model, batch_size=32)
    retriever = Retriever(vector_store=vs, embedding_model=model)
    builder = ContextBuilder(retriever=retriever, product_store=store)
    return store, builder


@ollama_available
def test_e2e_pv210_sухой_остаток():
    store, builder = _build()
    llm = OllamaLLM(base_url="http://10.201.0.9:11434")
    gen = AnswerGenerator(context_builder=builder, llm=llm)

    result = gen.answer("Какой сухой остаток у PV210?")
    assert result.has_answer is True
    assert result.refusal is False
    assert result.answer.strip(), "empty LLM answer"
    assert result.sources, "no sources"
    for s in result.sources:
        assert s.article == "PV210-XX"
        assert s.file and "PV210" in s.file
    # LLM-ответ не должен содержать выдуманного источника
    fake_files = ["fake.pdf", "test.pdf"]
    for ff in fake_files:
        assert ff not in result.answer


@ollama_available
def test_e2e_pa777_hardener():
    store, builder = _build()
    llm = OllamaLLM(base_url="http://10.201.0.9:11434")
    gen = AnswerGenerator(context_builder=builder, llm=llm)

    result = gen.answer("Какой отвердитель у PA777-9016?")
    assert result.has_answer is True
    assert result.sources
    for s in result.sources:
        assert s.article == "PA777-9016"


@ollama_available
def test_e2e_unknown_product_refusal_llm_not_called(monkeypatch):
    """XXX999 — отказ: LLM НЕ вызывается, has_answer=False."""
    store, builder = _build()
    llm_real = OllamaLLM(base_url="http://10.201.0.9:11434")
    gen = AnswerGenerator(context_builder=builder, llm=llm_real)

    # Считаем только запросы к /api/generate (LLM). Запросы к /api/embed
    # (встраивание вопроса) идут через реальную urlopen.
    llm_http_calls = []
    import paint_rag.rag.llm_ollama as _llm_mod
    from urllib.request import urlopen as _real_urlopen

    def _filtering(req, timeout=None):
        if getattr(req, "full_url", "") and req.full_url.endswith(
            "/api/generate"
        ):
            llm_http_calls.append(req)
            raise RuntimeError("LLM must NOT be called on refusal")
        return _real_urlopen(req, timeout=timeout)

    monkeypatch.setattr(_llm_mod.urlrequest, "urlopen", _filtering)

    result = gen.answer("Какой сухой остаток у XXX999?", article="XXX999")

    assert llm_http_calls == []
    assert result.has_answer is False
    assert result.refusal is True
    assert result.context_used is False
    assert result.sources == []

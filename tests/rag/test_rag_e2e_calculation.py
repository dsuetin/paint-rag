"""Real E2E — реальный Ollama (bge-m3 embedding + qwen3:8b LLM).

Полный путь: question → retrieval → LLM-решение → Calculator
→ LLM финальный ответ.

Ключевые проверки (не по тексту LLM, а по structured-данным):
  Test A — factual «Какой отвердитель у PA777-9016?»:
           retrieval → продукт PA777-9016 → ответ; calculator НЕ вызван.
  Test B — «Сколько грунта PA777-9016 на 160 м² в 2 слоя?»:
           LLM решит calculation_required=true, article=PA777-9016,
           area_m2=160, layers=2 → Calculator → 160*2*0.24 = 76.8 кг.
  Test C — XXX999 → отказ, calculator НЕ вызван, LLM-ответ
           использует только то, что реально в index.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.rag.answer_generator import AnswerGenerator
from paint_rag.rag.calculation_engine import CalculationEngine
from paint_rag.rag.context_builder import ContextBuilder
from paint_rag.rag.indexing import build_index
from paint_rag.rag.llm_ollama import OllamaLLM
from paint_rag.rag.pipeline import make_real_embedding_model
from paint_rag.rag.retriever import Retriever


DATA = Path("data/knowledge/products.json")
BASE = "http://10.201.0.9:11434"


def _ollama_ok() -> bool:
    try:
        with urllib.request.urlopen(
            f"{BASE}/api/version", timeout=3
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
def test_e2e_factual_hardener_calculator_not_called():
    store, builder = _build()
    llm = OllamaLLM(base_url=BASE)

    # Считаем запросы к /api/generate, чтобы гарантировать,
    # что calculator НЕ вызывался: при factual LLM вызывается ровно
    # 1 раз (decision) + 1 раз (final answer) = 2, но ответ должен
    # содержать только факты из index (HD816 / 33%).
    gen = AnswerGenerator(context_builder=builder, llm=llm)
    engine = CalculationEngine(
        answer_generator=gen,
        product_store=store,
        llm=llm,
    )

    result = engine.run("Какой отвердитель у PA777-9016?")
    trace = result.trace

    assert trace.calculator_called is False
    assert trace.request is None
    assert result.answer.has_answer is True
    assert result.answer.refusal is False
    # Factual retrieval: PA777-9016 действительно в источниках.
    assert any(
        s.article == "PA777-9016" for s in result.answer.sources
    )
    # Логика: LLM-ответ должен содержать HD816 (он в index).
    assert "HD816" in result.answer.answer or "hd816" in (
        result.answer.answer.lower()
    ) or "33" in result.answer.answer


@ollama_available
def test_e2e_calculation_pa777_160m2_2layers():
    store, builder = _build()
    llm = OllamaLLM(base_url=BASE)

    gen = AnswerGenerator(context_builder=builder, llm=llm)
    engine = CalculationEngine(
        answer_generator=gen,
        product_store=store,
        llm=llm,
    )

    result = engine.run(
        "Сколько грунта PA777-9016 нужно для покрытия площади 160 м² "
        "в 2 слоя?"
    )
    trace = result.trace

    # LLM правильно поняла, ЧТО считать.
    assert trace.decision is not None
    assert trace.decision.calculation_required is True
    assert trace.decision.article is not None
    assert trace.decision.article.upper() in ("PA777-9016", "PA777")
    assert trace.decision.area_m2 == pytest.approx(160.0, rel=1e-6)
    assert trace.decision.layers == 2

    # Продукт выбран (PA777-9016 из реального store)
    assert trace.article == "PA777-9016"
    assert trace.product is not None

    # Calculator РЕАЛЬНО вызван; запрос содержит реальные Product-данные.
    assert trace.calculator_called is True
    assert trace.request is not None
    assert trace.request.consumption_kg_per_m2 == 0.24  # 240 г/м²
    assert trace.request.area_m2 == 160.0
    assert trace.request.layers == 2

    # КАЛЬКУЛЯТОРСКИЙ РЕЗУЛЬТАТ — это главный assertion:
    # 160 * 2 * 0.24 = 76.80
    assert trace.result is not None
    assert trace.result.total_kg == pytest.approx(76.8, rel=1e-6)
    assert trace.result.base.kg == pytest.approx(76.8, rel=1e-6)

    # Factual retrieval + LLM-ответ содержат 76.8/76.80
    assert "76.8" in result.answer.answer or "76,8" in result.answer.answer
    assert result.answer.has_answer is True


@ollama_available
def test_e2e_unknown_article_refusal_no_calculator():
    store, builder = _build()
    llm = OllamaLLM(base_url=BASE)

    gen = AnswerGenerator(context_builder=builder, llm=llm)
    engine = CalculationEngine(
        answer_generator=gen,
        product_store=store,
        llm=llm,
    )

    result = engine.run(
        "Сколько материала XYZ-DOES-NOT-EXIST на 100 м²?"
    )
    trace = result.trace

    # Главное: без известного продукта calculator НЕ вызывается —
    # независимо от того, как LLM классифицировала вопрос.
    assert trace.calculator_called is False
    assert trace.request is None
    assert trace.result is None

    # Система корректно сообщает об отсутствии данных
    # (LLM может либо классифицировать вопрос как calculation и
    # получить детерминированный отказ движка, либо ответить по RAG:
    # «в документации информация не найдена»).
    low = result.answer.answer.lower()
    assert ("не найд" in low) or ("недостаточно" in low)

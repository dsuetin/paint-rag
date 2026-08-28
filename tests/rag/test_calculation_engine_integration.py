"""Integration-тесты: LLM-решение → Calculator (без реального Ollama).

FakeLLM возвращает детерминированный JSON-решение на decision-prompt и
финальный текст на answer-prompt. Retriever/VectorStore — настоящие,
ProductStore и LLM — фиксированные: проверяется не конечный текст, а
  calculation_required / article / area / calculator_called
  / точность calculation_result.
"""
from __future__ import annotations

from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.rag.answer_generator import AnswerGenerator
from paint_rag.rag.calculation_engine import CalculationEngine
from paint_rag.rag.context_builder import ContextBuilder
from paint_rag.rag.llm import FakeLLM
from paint_rag.rag.retriever import Retriever
from paint_rag.rag.vector_store import VectorStore

from conftest_pipeline import build_fixture


REAL_DATA = Path("data/knowledge/products.json")


def _store() -> ProductStore:
    """Реальный ProductStore: products.json (есть расход/variants)."""
    return ProductStore.from_json(REAL_DATA)


def _engine(decision_payload: str, final_text: str = "ok") -> tuple:
    """Возвращает (engine, llm, prompts).

    Retriever/VectorStore — фикстура (нужны для factual-пути);
    ProductStore — РЕАЛЬНЫЙ, чтобы у продуктов были расход/variants.
    """
    retriever, _fixture_store = build_fixture()
    store = _store()

    calls: list[str] = []

    def on_generate(prompt: str) -> str:
        calls.append(prompt)
        # decision-промпт содержит «СПИСОК ИЗВЕСТНЫХ ПРОДУКТОВ».
        if "СПИСОК ИЗВЕСТНЫХ ПРОДУКТОВ" in prompt:
            return decision_payload
        return final_text

    llm = FakeLLM(on_generate=on_generate)
    builder = ContextBuilder(retriever=retriever, product_store=store)
    generator = AnswerGenerator(context_builder=builder, llm=llm)
    engine = CalculationEngine(
        answer_generator=generator,
        product_store=store,
        llm=llm,
    )
    return engine, llm, calls


# ----------------------------------------------------------------------
# Test 1: question с расчётом → calculator вызван, верный продукт/площадь
# ----------------------------------------------------------------------


def test_calculation_question_calls_calculator():
    engine, _, calls = _engine(
        '{"calculation_required": true, "article": "PA777-9016", '
        '"area_m2": 160, "layers": 2}',
        "Нужно 76.80 кг на 2 слоя.",
    )

    result = engine.run("Сколько материала нужно на 160 м² для PA777-9016?")
    trace = result.trace

    assert trace.decision.calculation_required is True
    assert trace.decision.article == "PA777-9016"
    assert trace.decision.area_m2 == 160.0
    assert trace.decision.layers == 2

    assert trace.article == "PA777-9016"
    assert trace.product is not None

    # Калькулятор РЕАЛЬНО вызван
    assert trace.calculator_called is True
    assert trace.request is not None

    # Calculator получил реальный Product-расход: 240 г/м² = 0.24 кг/м²
    assert trace.request.consumption_kg_per_m2 == 0.24
    assert trace.request.area_m2 == 160.0
    assert trace.request.layers == 2

    # Математика: 160 * 2 * 0.24 = 76.8
    assert trace.result is not None
    assert trace.result.total_kg == 76.8
    assert trace.result.base.kg == 76.8

    # Final answer — от LLM-текста (LLM только формулирует)
    assert result.answer.has_answer is True
    assert "76.80" in result.answer.answer

    # LLM получила калькуляторский результат в prompt
    assert "ИТОГО: 76.8000 кг" in calls[-1]
    assert "НЕ выполняй арифметику" in calls[-1]


# ----------------------------------------------------------------------
# Test 2: слои не заданы LLM → берём max_layers из Product
# ----------------------------------------------------------------------


def test_calculation_layers_fallback_to_product_max_layers():
    engine, _, _ = _engine(
        '{"calculation_required": true, "article": "PA777-9016", '
        '"area_m2": 50, "layers": null}',
    )

    result = engine.run("Сколько краски нужно на 50 м²?")
    trace = result.trace

    assert trace.calculator_called is True
    assert trace.request.layers == 2  # max_layers PA777-9016
    assert trace.request.consumption_kg_per_m2 == 0.24
    # 50 * 2 * 0.24 = 24.0
    assert trace.result.total_kg == 24.0


# ----------------------------------------------------------------------
# Test 3: factual вопрос → calculator НЕ вызывается
# ----------------------------------------------------------------------


def test_factual_question_does_not_call_calculator():
    engine, _, calls = _engine(
        '{"calculation_required": false, "article": "PA777-9016", '
        '"area_m2": null, "layers": null}',
        "Отвердитель — HD816, 33% по весу.",
    )

    result = engine.run("Какой отвердитель у PA777-9016?")
    trace = result.trace

    assert trace.decision.calculation_required is False
    assert trace.calculator_called is False
    assert trace.request is None
    assert trace.result is None


# ----------------------------------------------------------------------
# Test 4: fuzzy артикул (PV21O) → корректный продукт PV210-XX
# ----------------------------------------------------------------------


def test_fuzzy_article_resolves_correct_product():
    engine, _, _ = _engine(
        # LLM «написала» PV21O (ошибка) — движок подбирает PV210-XX.
        '{"calculation_required": true, "article": "PV21O", '
        '"area_m2": 10, "layers": 1}',
    )

    result = engine.run("Сколько лака нужно на 10 м²?")
    trace = result.trace

    assert trace.calculator_called is True
    assert trace.article == "PV210-XX"
    # PV210: расход 120–160 г/м² -> максимум 160 -> 0.16 кг/м²
    assert trace.request.consumption_kg_per_m2 == 0.16
    assert trace.result.total_kg == 10 * 1 * 0.16


# ----------------------------------------------------------------------
# Test 5: PV29O (опечатка) → PV290-99
# ----------------------------------------------------------------------


def test_pv29o_typo_resolves_to_pv290():
    engine, _, _ = _engine(
        '{"calculation_required": true, "article": "PV29O", '
        '"area_m2": 5, "layers": 1}',
    )

    result = engine.run("Сколько лака нужно на 5 м²?")
    trace = result.trace

    assert trace.calculator_called is True
    assert trace.article == "PV290-99"
    # PV290: 100–160 г/м² -> 0.16 кг/м²
    assert trace.request.consumption_kg_per_m2 == 0.16
    assert trace.result.total_kg == 5 * 160 / 1000


# ----------------------------------------------------------------------
# Test 6: несуществующий артикул → отказ, calculator НЕ вызывается
# ----------------------------------------------------------------------


def test_unknown_product_refusal_no_calculator():
    engine, _, _ = _engine(
        '{"calculation_required": true, "article": "XXX999", '
        '"area_m2": 100, "layers": 2}',
    )

    result = engine.run("Сколько материала XXX999 нужно на 100 м²?")
    trace = result.trace

    assert trace.decision.calculation_required is True
    assert trace.product is None
    assert trace.calculator_called is False
    assert trace.request is None
    assert trace.result is None
    assert trace.error is not None

    assert result.answer.refusal is True
    assert result.answer.has_answer is False


# ----------------------------------------------------------------------
# Test 7: площадь не указана → уточняющий отказ, calculator НЕ вызывается
# ----------------------------------------------------------------------


def test_missing_area_refusal_no_calculator():
    engine, _, _ = _engine(
        '{"calculation_required": true, "article": "PA777-9016", '
        '"area_m2": null, "layers": null}',
    )

    result = engine.run("Сколько краски нужно для PA777-9016?")
    trace = result.trace

    assert trace.decision.calculation_required is True
    assert trace.product is not None  # продукт нашли
    assert trace.calculator_called is False
    assert trace.request is None
    assert result.answer.refusal is True


# ----------------------------------------------------------------------
# Test 8: финальный prompt LLM содержит результат калькулятора
# ----------------------------------------------------------------------


def test_final_llm_prompt_contains_calculator_result():
    engine, _, calls = _engine(
        '{"calculation_required": true, "article": "PA777-9016", '
        '"area_m2": 3, "layers": 2}',
        "2 слоя по 3 м²: итого 1.44 кг.",
    )

    engine.run("Сколько краски на 3 м²?")

    final_prompt = calls[-1]
    # 3 * 2 * 0.24 = 1.44 кг — посчитал калькулятор, не LLM
    assert "ИТОГО: 1.4400 кг" in final_prompt
    assert "НЕ выполняй арифметику" in final_prompt

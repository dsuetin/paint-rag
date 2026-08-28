from __future__ import annotations

from dataclasses import dataclass, field

from paint_rag.rag.answer_result import AnswerResult
from paint_rag.tools.calculator import (
    CalculationResult,
)


@dataclass
class Decision:
    """Структурированное решение LLM: нужен ли расчёт, какой продукт,
    какая площадь и сколько слоёв.

    ``raw`` — оригинальный текст ответа LLM (для отладки и трейса).
    """

    calculation_required: bool = False
    article: str | None = None
    area_m2: float | None = None
    layers: int | None = None
    raw: str = ""


@dataclass
class CalculationRequest:
    """Контракт между движком и калькулятором:
    только параметры; арифметика — в :func:`calculate_from_reference`."""

    article: str
    product_name: str
    area_m2: float
    layers: int
    consumption_kg_per_m2: float


@dataclass
class CalculationTrace:
    """Наблюдаемое прохождение вопроса через движок:
    decision → retrieval → продукт → расчёт → финальный ответ."""

    query: str
    decision: Decision | None = None
    retrieval_articles: list[str] = field(default_factory=list)
    product: str | None = None
    article: str | None = None
    calculation_required: bool = False
    calculator_called: bool = False
    request: CalculationRequest | None = None
    result: CalculationResult | None = None
    error: str | None = None


@dataclass
class EngineResult:
    """Итог работы движка: RAG-ответ (:class:`AnswerResult`) + трейс."""

    answer: AnswerResult
    trace: CalculationTrace


def _component_dict(component) -> dict | None:
    if component is None:
        return None
    return {"kg": component.kg, "cost": component.cost}


def calculation_result_to_dict(result: CalculationResult) -> dict:
    """Сериализация :class:`CalculationResult` в словарь (для трейса)."""
    return {
        "area_m2": result.area_m2,
        "layers": result.layers,
        "base": _component_dict(result.base),
        "hardener": _component_dict(result.hardener),
        "thinner": _component_dict(result.thinner),
        "total_kg": result.total_kg,
        "total_cost": result.total_cost,
    }

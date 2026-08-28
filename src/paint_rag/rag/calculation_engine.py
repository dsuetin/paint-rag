from __future__ import annotations

import json
import re

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.rag.answer_generator import AnswerGenerator
from paint_rag.rag.answer_result import AnswerResult
from paint_rag.rag.calculation_trace import (
    CalculationRequest,
    CalculationTrace,
    Decision,
    EngineResult,
    calculation_result_to_dict,
)
from paint_rag.rag.context_builder import detect_article
from paint_rag.rag.llm import LLM, LLMGenerationError
from paint_rag.rag.prompt_builder import (
    build_calculation_answer_prompt,
    build_decision_prompt,
)
from paint_rag.tools.calculator import (
    NoCalculationDataError,
    calculate_from_reference,
    resolve_consumption,
)


_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_decision(text: str) -> Decision:
    """Разобрать ответ LLM (JSON) в :class:`Decision`.

    Устойчив к лишнему тексту до/объекта и к ``null``-полями.
    Неудачный парс — безопасный ``calculation_required=False``
    (калькулятор вызывать нельзя: параметров нет).
    """
    decision = Decision(raw=text or "")
    if not text:
        return decision

    match = _JSON_OBJ_RE.search(text)
    if not match:
        return decision

    try:
        data = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return decision

    if not isinstance(data, dict):
        return decision

    required = data.get("calculation_required")
    decision.calculation_required = required is True

    article = data.get("article")
    if isinstance(article, str) and article.strip():
        decision.article = article.strip()

    area = data.get("area_m2")
    if isinstance(area, (int, float)) and not isinstance(area, bool):
        decision.area_m2 = float(area)

    layers = data.get("layers")
    if isinstance(layers, (int, float)) and not isinstance(layers, bool):
        if float(layers).is_integer() and layers > 0:
            decision.layers = int(layers)

    return decision


class LLMDecider:
    """Адаптер :class:`LLM` → :class:`Decision`.

    Это единственное место, где LLM участвует в решении
    «нужен ли расчёт»: она НЕ считает, а лишь извлекает
    структурированные параметры.
    """

    def __init__(self, llm: LLM) -> None:
        self.llm = llm

    def decide(self, decision_prompt: str) -> Decision:
        return parse_decision(self.llm.generate(decision_prompt))


def _known_product_lines(store: ProductStore) -> list[str]:
    lines = []
    for product in store.all():
        article = product.article or "—"
        lines.append(f"{article} — {product.name}")
    return lines


def _match_product(
    store: ProductStore,
    article: str | None,
) -> "tuple[object, str] | None":
    """Матч продукта по article из решения LLM (exact → fuzzy)."""
    if not article:
        return None

    exact = store.get_by_article(article)
    if exact is not None:
        return exact, exact.article or article

    match = (
        store.get(article)
        if article.lower().strip()
        else None
    )
    if match is not None:
        return match, match.article or article

    fuzzy = detect_article(article, store)
    if fuzzy is not None:
        product = store.get_by_article(fuzzy)
        if product is not None:
            return product, product.article or fuzzy

    return None


class CalculationEngine:
    """Первый полноценный end-to-end движок:

    question
      → LLM decision (нужен ли расчёт, article, area, layers)
      → при расчёте: product store → детерминированный Calculator
      → LLM финализирует текст ответа, НЕ выполняя арифметику.

    Фактические вопросы (``calculation_required=False``) идут
    обычным путём AnswerGenerator; калькулятор НЕ вызывается.
    """

    def __init__(
        self,
        *,
        answer_generator: AnswerGenerator,
        product_store: ProductStore,
        llm: LLM,
        decider: LLMDecider | None = None,
        calculator=calculate_from_reference,
    ) -> None:
        self.answer_generator = answer_generator
        self.product_store = product_store
        self.llm = llm
        self.decider = decider or LLMDecider(llm)
        self.calculator = calculator

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, query: str) -> EngineResult:
        decision_prompt = build_decision_prompt(
            query,
            _known_product_lines(self.product_store),
        )
        decision = self.decider.decide(decision_prompt)

        if not decision.calculation_required:
            answer = self._answer_factually(query)
            trace = CalculationTrace(
                query=query,
                decision=decision,
                retrieval_articles=[
                    s.article
                    for s in answer.sources
                    if s.article is not None
                ],
                calculation_required=False,
                calculator_called=False,
            )
            return EngineResult(answer=answer, trace=trace)

        return self._run_calculation(
            query=query,
            decision=decision,
        )

    # ------------------------------------------------------------------
    # Factual path
    # ------------------------------------------------------------------

    def _answer_factually(self, query: str) -> AnswerResult:
        return self.answer_generator.answer(query)

    # ------------------------------------------------------------------
    # Calculation path
    # ------------------------------------------------------------------

    def _run_calculation(
        self,
        *,
        query: str,
        decision: Decision,
    ) -> EngineResult:
        trace = CalculationTrace(
            query=query,
            decision=decision,
            calculation_required=True,
        )

        product_match = _match_product(
            self.product_store,
            decision.article,
        )

        if product_match is None:
            trace.error = "Продукт не найден"
            self._attach_factual_articles(trace, query)
            return EngineResult(
                answer=self._refusal_answer(
                    query,
                    "Недостаточно данных: продукт не найден.",
                ),
                trace=trace,
            )

        product, article = product_match
        trace.product = product.name
        trace.article = article or decision.article

        area = decision.area_m2
        if area is None or area <= 0:
            trace.error = "Не указана площадь"
            return EngineResult(
                answer=self._refusal_answer(
                    query,
                    "Недостаточно данных: укажите площадь в м².",
                ),
                trace=trace,
            )

        try:
            consumption = resolve_consumption(
                product,
                article=article,
            )
        except NoCalculationDataError as exc:
            trace.error = str(exc)
            return EngineResult(
                answer=self._refusal_answer(
                    query,
                    f"Недостаточно данных для расчёта: {exc}",
                ),
                trace=trace,
            )

        layers = (
            decision.layers
            if decision.layers is not None and decision.layers > 0
            else (
                product.max_layers
                if product.max_layers is not None
                and product.max_layers > 0
                else 1
            )
        )

        request = CalculationRequest(
            article=article or "",
            product_name=product.name,
            area_m2=float(area),
            layers=int(layers),
            consumption_kg_per_m2=consumption,
        )

        result = self.calculator(
            area_m2=request.area_m2,
            layers=request.layers,
            reference={"base": {"kg": request.consumption_kg_per_m2}},
        )

        trace.calculator_called = True
        trace.request = request
        trace.result = result

        final_prompt = build_calculation_answer_prompt(
            query=query,
            product_line=f"{request.product_name} ({request.article})",
            calculation_lines=_result_lines(
                result,
                calculation_result_to_dict(result),
            ),
        )

        try:
            answer_text = self.llm.generate(final_prompt)
        except LLMGenerationError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LLMGenerationError(
                f"LLM generation failed: {exc}"
            ) from exc

        if not answer_text or not answer_text.strip():
            answer = AnswerResult(
                query=query,
                answer=(
                    "Расчёт выполнен калькулятором, но "
                    "генерация текстового ответа завершилась "
                    "без результата."
                ),
                has_answer=False,
                refusal=True,
            )
        else:
            answer = AnswerResult(
                query=query,
                answer=answer_text,
                has_answer=True,
                context_used=True,
                refusal=False,
            )

        return EngineResult(answer=answer, trace=trace)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refusal_answer(self, query: str, message: str) -> AnswerResult:
        return AnswerResult(
            query=query,
            answer=message,
            sources=[],
            has_answer=False,
            context_used=False,
            refusal=True,
        )

    def _attach_factual_articles(
        self,
        trace: CalculationTrace,
        query: str,
    ) -> None:
        try:
            context = self.answer_generator.context_builder.build(query)
        except Exception:  # noqa: BLE001
            return
        trace.retrieval_articles = [
            s.article for s in context.sources if s.article is not None
        ]


def _result_lines(result, result_dict) -> list[str]:
    """Человекочитаемые строки калькуляторского результата —
    то, что попадает в финальный prompt LLM."""
    base = result_dict["base"] or {}
    lines = [
        f"Площадь: {result_dict['area_m2']:.4g} м²",
        f"Слои: {result_dict['layers']}",
        f"Основной компонент: {base.get('kg', 0):.4f} кг",
        f"ИТОГО: {result_dict['total_kg']:.4f} кг",
    ]
    if result_dict.get("total_cost") is not None:
        lines.append(
            f"ИТОГО стоимость: {result_dict['total_cost']:.2f} руб."
        )
    hardener = result_dict.get("hardener")
    if hardener:
        lines.append(
            f"Отвердитель: {hardener['kg']:.4f} кг"
        )
    thinner = result_dict.get("thinner")
    if thinner:
        lines.append(f"Разбавитель: {thinner['kg']:.4f} кг")
    return lines

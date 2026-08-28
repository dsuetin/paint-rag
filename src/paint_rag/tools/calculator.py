from __future__ import annotations

from dataclasses import dataclass


class NoCalculationDataError(ValueError):
    """У продукта нет данных, достаточных для расчёта
    (ни ``consumption`` в г/м², ни ``calculation_reference``
    ни в одном варианте)."""


def resolve_consumption(
    product,
    *,
    article: str | None = None,
) -> float:
    """Детерминированно извлечь расход продукта в **кг/м² на слой**
    из его реальных свойств (без участия LLM).

    Приоритет источников (оба — реальные данные Product):

    1. ``product.consumption_min`` / ``consumption_max``
       + ``consumption_unit == "g_per_m2"``:
       берём максимум (консервативная оценка расхода);
    2. ``calculation_reference.base.kg`` у подходящего варианта
       (``article`` — точное совпадение с article варианта,
       иначе первый вариант с reference).

    Всё, что не ``g_per_m2`` (``m2_per_kg``, ``ml_per_m2``,
    ``microns_per_layer`` и т.д.), трактуется как
    неконвертируемое — для него нет надёжного расчёта.

    :raises NoCalculationDataError: пригодных данных нет.
    """
    if (
        product.consumption_unit == "g_per_m2"
        and product.consumption_max is not None
    ):
        value = product.consumption_max
    elif (
        product.consumption_unit == "g_per_m2"
        and product.consumption_min is not None
    ):
        value = product.consumption_min
    else:
        value = None

    if value is not None:
        return value / 1000.0

    variants = product.variants or []

    if article:
        wanted = article.lower().strip()
        for variant in variants:
            if (
                variant.article
                and variant.article.lower().strip() == wanted
            ):
                variants = [variant]
                break

    for variant in variants:
        reference = variant.calculation_reference
        if reference is None or reference.base is None:
            continue
        if reference.base.kg is None:
            raise NoCalculationDataError(
                "calculation_reference.base.kg отсутствует"
            )
        return float(reference.base.kg)

    raise NoCalculationDataError(
        "У продукта нет расхода в г/м² и нет "
        "calculation_reference"
    )


@dataclass
class ComponentResult:
    kg: float
    cost: float | None


@dataclass
class CalculationResult:
    area_m2: float
    layers: int

    base: ComponentResult
    hardener: ComponentResult | None
    thinner: ComponentResult | None

    total_kg: float
    total_cost: float | None


def calculate_from_reference(
    *,
    area_m2: float,
    layers: int,
    reference: dict,
) -> CalculationResult:

    if area_m2 <= 0:
        raise ValueError(
            "Площадь должна быть больше 0"
        )

    if layers <= 0:
        raise ValueError(
            "Количество слоёв должно быть больше 0"
        )

    multiplier = area_m2 * layers

    base_ref = reference["base"]

    base_kg = (
        base_ref["kg"]
        * multiplier
    )

    base_cost = None

    if base_ref.get("cost") is not None:
        base_cost = (
            base_ref["cost"]
            * multiplier
        )

    # --------------------------------------------------
    # Hardener
    # --------------------------------------------------

    hardener = None

    hardener_ref = reference.get(
        "hardener"
    )

    if hardener_ref:

        hardener_kg = (
            hardener_ref["kg"]
            * multiplier
        )

        hardener_cost = None

        if hardener_ref.get("cost") is not None:
            hardener_cost = (
                hardener_ref["cost"]
                * multiplier
            )

        hardener = ComponentResult(
            kg=hardener_kg,
            cost=hardener_cost,
        )

    # --------------------------------------------------
    # Thinner
    # --------------------------------------------------

    thinner = None

    thinner_ref = reference.get(
        "thinner"
    )

    if thinner_ref:

        thinner_kg = (
            thinner_ref["kg"]
            * multiplier
        )

        thinner_cost = None

        if thinner_ref.get("cost") is not None:
            thinner_cost = (
                thinner_ref["cost"]
                * multiplier
            )

        thinner = ComponentResult(
            kg=thinner_kg,
            cost=thinner_cost,
        )

    # --------------------------------------------------
    # Total
    # --------------------------------------------------

    total_kg = base_kg

    if hardener:
        total_kg += hardener.kg

    if thinner:
        total_kg += thinner.kg

    costs = []

    if base_cost is not None:
        costs.append(base_cost)

    if hardener and hardener.cost is not None:
        costs.append(hardener.cost)

    if thinner and thinner.cost is not None:
        costs.append(thinner.cost)

    total_cost = (
        sum(costs)
        if costs
        else None
    )

    return CalculationResult(
        area_m2=area_m2,
        layers=layers,

        base=ComponentResult(
            kg=base_kg,
            cost=base_cost,
        ),

        hardener=hardener,
        thinner=thinner,

        total_kg=total_kg,
        total_cost=total_cost,
    )
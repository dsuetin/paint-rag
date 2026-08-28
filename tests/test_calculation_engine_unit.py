"""Unit-тесты детерминированных частей E2E-движка:

- :func:`paint_rag.rag.calculation_engine.parse_decision`
- :func:`paint_rag.tools.calculator.resolve_consumption`

LLM здесь НЕ участвует.
"""
from pathlib import Path

import pytest

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.rag.calculation_engine import parse_decision
from paint_rag.tools.calculator import (
    NoCalculationDataError,
    resolve_consumption,
)

DATA = Path("data/knowledge/products.json")


def _store() -> ProductStore:
    return ProductStore.from_json(DATA)


# ----------------------------------------------------------------------
# parse_decision
# ----------------------------------------------------------------------


def test_parse_decision_calculation_true():
    d = parse_decision(
        '{"calculation_required": true, "article": "PA777-9016", '
        '"area_m2": 160, "layers": 2}'
    )
    assert d.calculation_required is True
    assert d.article == "PA777-9016"
    assert d.area_m2 == 160.0
    assert d.layers == 2


def test_parse_decision_calculation_false():
    d = parse_decision(
        '{"calculation_required": false, "article": "PA777-9016", '
        '"area_m2": null, "layers": null}'
    )
    assert d.calculation_required is False
    assert d.article == "PA777-9016"
    assert d.area_m2 is None
    assert d.layers is None


def test_parse_decision_embedded_json():
    d = parse_decision(
        'Конечно, вот решение: '
        '{"calculation_required": true, "article": "PV290-99", '
        '"area_m2": 100, "layers": null} '
        'Готово.'
    )
    assert d.calculation_required is True
    assert d.article == "PV290-99"
    assert d.area_m2 == 100.0
    assert d.layers is None


def test_parse_decision_garbage_is_safe_noop():
    d = parse_decision("вообще не json")
    assert d.calculation_required is False
    assert d.article is None
    assert d.area_m2 is None
    assert d.layers is None


def test_parse_decision_empty():
    d = parse_decision("")
    assert d.calculation_required is False


def test_parse_decision_bool_not_area():
    d = parse_decision(
        '{"calculation_required": true, "article": "X", '
        '"area_m2": true, "layers": true}'
    )
    assert d.calculation_required is True
    # bool не проходит как число:
    assert d.area_m2 is None
    assert d.layers is None


# ----------------------------------------------------------------------
# resolve_consumption
# ----------------------------------------------------------------------


def test_resolve_consumption_from_product_consumption():
    product = _store().get_by_article("PA777-9016")
    assert product is not None
    # 240 г/м² -> 0.24 кг/м²
    assert resolve_consumption(product) == pytest.approx(0.24)


def test_resolve_consumption_pv210_range():
    product = _store().get_by_article("PV210-XX")
    assert product is not None
    # consumption: 120–160 г/м² -> берём максимум 160 -> 0.16 кг/м²
    assert resolve_consumption(product) == pytest.approx(0.16)


def test_resolve_consumption_from_variant_reference():
    product = _store().get_by_article("PD155")
    assert product is not None
    # из calculation_reference.base.kg у варианта
    expected = (
        product.variants[0].calculation_reference.base.kg
    )
    assert resolve_consumption(product) == pytest.approx(expected)


def test_resolve_consumption_no_data_raises():
    from paint_rag.models.product import Product

    product = Product(name="Без данных")
    with pytest.raises(NoCalculationDataError):
        resolve_consumption(product)

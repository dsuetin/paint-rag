from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore

DATA = Path("data/knowledge/products.json")


def _store():
    return ProductStore.from_json(DATA)


def test_pv290_exists():
    p = _store().get_by_article("PV290-99")
    assert p is not None
    assert p.name == "Лак PV290"
    assert p.technology == "Rupa"
    assert "PV290" in p.aliases


def test_pv290_consumption():
    p = _store().get_by_article("PV290-99")
    assert p.consumption_min == 100.0
    assert p.consumption_max == 160.0


def test_pv290_mixing():
    p = _store().get_by_article("PV290-99")
    m = p.mixing
    assert m.hardener.name == "HD860"
    assert m.hardener.percent == 30
    assert m.thinner_ratio.min == 20
    assert m.thinner_ratio.max == 40


def test_pv290_alternative_hardener():
    p = _store().get_by_article("PV290-99")
    assert "HD830" in p.mixing.raw


def test_pv290_variants_empty():
    p = _store().get_by_article("PV290-99")
    assert p.variants == []

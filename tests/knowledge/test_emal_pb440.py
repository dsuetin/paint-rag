from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore

DATA = Path("data/knowledge/products.json")


def _store():
    return ProductStore.from_json(DATA)


def test_pb440_exists():
    p = _store().get_by_article("PB440-XX")
    assert p is not None
    assert p.name == "Эмаль PB440"
    assert p.technology == "Rupa"


def test_pb440_consumption_layers():
    p = _store().get_by_article("PB440-XX")
    assert p.consumption_min == 120.0
    assert p.consumption_max == 140.0
    assert p.max_layers == 2


def test_pb440_mixing():
    p = _store().get_by_article("PB440-XX")
    m = p.mixing
    assert m.hardener.name == "HD844"
    assert m.hardener.percent == 50
    assert m.thinner_ratio.min == 15
    assert m.thinner_ratio.max == 30


def test_pb440_variants_empty():
    p = _store().get_by_article("PB440-XX")
    assert p.variants == []

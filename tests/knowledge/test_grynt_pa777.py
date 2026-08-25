from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore

DATA = Path("data/knowledge/products.json")


def _store():
    return ProductStore.from_json(DATA)


def test_pa777_exists():
    p = _store().get_by_article("PA777-9016")
    assert p is not None
    assert p.name == "Грунт PA777-9016 эластичный"
    assert p.technology == "Rupa"
    assert "PA777" in p.aliases


def test_pa777_consumption_and_layers():
    p = _store().get_by_article("PA777-9016")
    assert p.consumption_max == 240.0
    assert p.consumption_unit == "g_per_m2"
    assert p.max_layers == 2


def test_pa777_mixing():
    p = _store().get_by_article("PA777-9016")
    m = p.mixing
    assert m is not None
    assert m.base_percent == 100
    assert m.hardener.name == "HD816"
    assert m.hardener.percent == 33
    assert m.thinner_ratio.min == 15
    assert m.thinner_ratio.max == 30


def test_pa777_variants_empty_and_source():
    p = _store().get_by_article("PA777-9016")
    assert p.variants == []


def test_pa777_source_points_to_pdf():
    import json

    data = json.loads(DATA.read_text(encoding="utf-8"))

    (item,) = [x for x in data if x["name"] == "Грунт PA777-9016 эластичный"]

    assert (
        item["source"]["file"]
        == "Rupa_PA777_9016_Белый_ПУ_грунт_эластичный.pdf"
    )
    assert item["source"]["page"] == 1

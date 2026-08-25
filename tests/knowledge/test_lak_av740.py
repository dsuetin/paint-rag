from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore

DATA = Path("data/knowledge/products.json")


def _store():
    return ProductStore.from_json(DATA)


def test_av740_exists():
    p = _store().get_by_article("AV740-XX")
    assert p is not None
    assert p.name == "Лак AV740"
    assert p.technology == "Rupa"
    assert "AV740" in p.aliases


def test_av740_consumption_and_layers():
    p = _store().get_by_article("AV740-XX")
    assert p.consumption_min == 120.0
    assert p.consumption_max == 140.0
    assert p.max_layers == 2


def test_av740_mixing():
    p = _store().get_by_article("AV740-XX")
    m = p.mixing
    assert m.hardener.name == "HA890"
    assert m.hardener.percent == 10
    assert m.thinner_ratio.min == 15
    assert m.thinner_ratio.max == 30


def test_av740_variants_empty():
    p = _store().get_by_article("AV740-XX")
    assert p.variants == []


def test_av740_source_points_to_pdf():
    import json

    data = json.loads(DATA.read_text(encoding="utf-8"))

    (item,) = [x for x in data if x["name"] == "Лак AV740"]

    assert (
        item["source"]["file"]
        == "Rupa_AV740_XX_Прозрачный_акриловый_лак_самогрунтующийся_2.pdf"
    )
    assert item["source"]["page"] == 1

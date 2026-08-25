from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore

DATA = Path("data/knowledge/products.json")


def _store():
    return ProductStore.from_json(DATA)


def test_wax092_exists():
    p = _store().get_by_article("WAX 092")
    assert p is not None
    assert p.name == "Масло-воск для террас WAX 092"
    assert p.technology == "OSWALD"


def test_wax092_consumption():
    p = _store().get_by_article("WAX 092")
    assert p.consumption_min == 50.0
    assert p.consumption_max == 90.0
    assert p.consumption_unit == "g_per_m2"


def test_wax092_variants_empty():
    p = _store().get_by_article("WAX 092")
    assert p.variants == []


def test_wax092_source_points_to_pdf():
    import json

    data = json.loads(DATA.read_text(encoding="utf-8"))

    (item,) = [x for x in data if x["name"] == "Масло-воск для террас WAX 092"]

    assert "092" in item["source"]["file"]
    assert item["source"]["page"] == 1

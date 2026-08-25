from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore

DATA = Path("data/knowledge/products.json")


def _store():
    return ProductStore.from_json(DATA)


def test_wt810_exists():
    p = _store().get_by_article("WT 810")
    assert p is not None
    assert p.name.startswith("Лак интерьерный")
    assert p.technology == "OSWALD"
    assert "WT 810" in p.aliases


def test_wt810_consumption():
    p = _store().get_by_article("WT 810")
    assert p.consumption_min == 100.0
    assert p.consumption_max == 125.0
    assert p.consumption_unit == "g_per_m2"


def test_wt810_variants_empty_and_source():
    p = _store().get_by_article("WT 810")
    assert p.variants == []


def test_wt810_source_points_to_pdf():
    import json

    data = json.loads(DATA.read_text(encoding="utf-8"))

    (item,) = [x for x in data if x["name"] == "Лак интерьерный DÉCO INTERIO WT 810"]

    assert "WT 810" in item["source"]["file"]
    assert item["source"]["page"] == 1

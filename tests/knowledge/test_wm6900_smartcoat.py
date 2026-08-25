from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore

DATA = Path("data/knowledge/products.json")


def _store():
    return ProductStore.from_json(DATA)


def test_wm6900_exists():
    p = _store().get_by_article("WM 6900-02")
    assert p is not None
    assert p.name == "Изолятор Cetol WM 6900-02"
    assert p.technology == "AkzoNobel Sikkens"
    assert "WM 6900-02" in p.aliases


def test_wm6900_consumption():
    p = _store().get_by_article("WM 6900-02")
    assert p.consumption_min == 100.0
    assert p.consumption_max == 150.0
    assert p.consumption_unit == "ml_per_m2"


def test_wm6900_thinner_range():
    p = _store().get_by_article("WM 6900-02")
    assert p.mixing.thinner_ratio.min == 15
    assert p.mixing.thinner_ratio.max == 20


def test_wm6900_source():
    import json

    data = json.loads(DATA.read_text(encoding="utf-8"))
    (item,) = [x for x in data if x["name"] == "Изолятор Cetol WM 6900-02"]
    assert item["source"]["file"] == "Изолятор WM_6900-02.pdf"
    assert item["source"]["page"] == 1


def test_smartcoat_wm690_exists():
    p = _store().get_by_article("WM 690")
    assert p is not None
    assert p.name == "Эмаль SMARTCOAT WM 690"
    assert p.technology == "OSWALD"
    assert "WM 690" in p.aliases


def test_smartcoat_wm690_consumption():
    p = _store().get_by_article("WM 690")
    assert p.consumption_min == 80.0
    assert p.consumption_max == 150.0
    assert p.consumption_unit == "g_per_m2"

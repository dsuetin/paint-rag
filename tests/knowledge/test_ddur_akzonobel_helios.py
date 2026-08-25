from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore

DATA = Path("data/knowledge/products.json")


def _store():
    return ProductStore.from_json(DATA)


def test_grunt_ddur_primer_article_and_mixing():
    store = _store()
    p = store.get("Грунт Д-ДУР Плюс Белый")
    assert p is not None
    assert "1149" in p.aliases
    assert "1149" in (p.article or "")
    m = p.mixing
    assert m is not None
    # Соотношение 10 : 3 : 2-5 => 30% и 20-50%
    assert m.hardener_ratio.min == 30
    assert m.hardener_ratio.max == 30
    assert m.thinner_ratio.min == 20
    assert m.thinner_ratio.max == 50


def test_emal_ddur_01_article_and_mixing():
    store = _store()
    p = store.get_by_article("2675-755251")
    assert p is not None
    assert p.name == "Эмаль Д-ДУР-01"
    assert "D-DUR WHITE 01" in p.aliases
    m = p.mixing
    assert m.hardener_ratio.min == 30
    assert m.thinner_ratio.min == 20
    assert m.thinner_ratio.max == 50


def test_lak_ddur_alias_both_articles():
    store = _store()
    p = store.get("Лак Д-ДУР")
    assert p is not None
    assert "2575-001251-200" in p.aliases
    assert "2575-001251-180" in p.aliases


def test_heliodur_anr_article_mixing_consumption():
    store = _store()
    p = store.get("Лак-Акриловый HELIODUR ANR")
    assert p is not None
    assert "HELIODUR ANR" in p.aliases
    # A/B = 10:1 => 10% отвердителя
    assert p.mixing.hardener_ratio.min == 10
    # Разбавитель 20-30%
    assert p.mixing.thinner_ratio.min == 20
    assert p.mixing.thinner_ratio.max == 30
    assert p.consumption_min == 100.0
    assert p.consumption_max == 120.0


def test_aqualit_article_and_mixing():
    store = _store()
    p = store.get_by_article("A-PT240-05")
    assert p is not None
    assert p.name == "Лак ПУ Паркетный"
    assert "Aqualit" in " ".join(p.aliases)
    assert p.mixing.hardener_ratio.min == 10
    assert p.mixing.thinner_ratio.min == 5
    assert p.mixing.thinner_ratio.max == 10
    assert p.consumption_min == 90.0
    assert p.consumption_max == 120.0

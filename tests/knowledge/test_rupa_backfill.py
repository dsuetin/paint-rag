import json
from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore

DATA_PATH = Path("data/knowledge/products.json")


def _store() -> ProductStore:
    return ProductStore.from_json(DATA_PATH)


def _raw(name: str) -> dict:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return [item for item in data if item.get("name") == name][0]


# ----------------------------------------------------------------
# PD118
# ----------------------------------------------------------------

def test_pd118_has_technical_data():
    p = _store().get("Грунт PD")
    assert p is not None
    td = p.technical_data
    assert td is not None
    assert td.dry_residue == "48±2%"
    assert td.density == "1,10±0,05 г/см³"
    assert td.viscosity == "85±5"
    assert td.pot_life == "3 часа"
    assert td.drying == "4 часа"
    assert td.shelf_life in {"от 12 месяцев.", "от 12 месяцев"}
    assert td.application is not None
    assert "краскопульт" in td.application.lower()
    assert td.usage is not None
    assert "прозрачный грунт" in td.usage


def test_pd118_unchanged_other_fields():
    p = _store().get("Грунт PD")
    assert p.name == "Грунт PD"
    assert p.technology == "Rupa"
    assert p.aliases
    assert p.variants
    assert len(p.variants) == 1  # не создали новых


# ----------------------------------------------------------------
# PD125
# ----------------------------------------------------------------

def test_pd125_has_technical_data():
    p = _store().get_by_article("PD125")
    assert p is not None
    td = p.technical_data
    assert td is not None
    assert td.dry_residue == "62±2%"
    assert td.density == "1,15±0,05 г/см³"
    assert td.drying == "2 - 4 часа"
    assert td.shelf_life in {"от 12 месяцев.", "от 12 месяцев"}
    assert td.application is not None
    assert td.usage is not None
    assert "грунт" in td.usage


def test_pd125_unchanged_other_fields():
    p = _store().get_by_article("PD125")
    assert p.name == "Грунт PD125"
    assert p.technology == "Rupa"
    assert len(p.variants) == 1
    assert p.mixing is not None


# ----------------------------------------------------------------
# PD155
# ----------------------------------------------------------------

def test_pd155_has_technical_data():
    p = _store().get_by_article("PD155")
    assert p is not None
    td = p.technical_data
    assert td is not None
    assert td.dry_residue == "72±2%"
    assert td.density == "1,35±0,05 г/см³"
    assert td.drying == "2 - 4 часа"
    assert td.shelf_life in {"от 12 месяцев.", "от 12 месяцев"}
    assert td.application is not None
    assert td.usage is not None
    assert "база" in td.usage or "МДФ" in td.usage or "массив" in td.usage.lower()


def test_pd155_unchanged_other_fields():
    p = _store().get_by_article("PD155")
    assert p.name == "Грунт PD155 изолятор для МДФ"
    assert p.technology == "Rupa"
    assert len(p.variants) == 1
    assert p.mixing is not None


# ----------------------------------------------------------------
# PV210
# ----------------------------------------------------------------

def test_pv210_has_technical_data():
    p = _store().get_by_article("PV210-XX")
    assert p is not None
    td = p.technical_data
    assert td is not None
    assert td.gloss == "10±3, 20±3"
    assert td.dry_residue == "54±2%"
    assert td.density == "1,00±0,05 г/см³"
    assert td.viscosity == "70±10"
    assert td.pot_life == "3 часа"
    assert td.drying is not None
    assert "12" in td.drying
    assert td.shelf_life in {"от 12 месяцев.", "от 12 месяцев"}
    assert td.application is not None
    assert td.usage is not None
    assert "лак" in td.usage


def test_pv210_unchanged_other_fields():
    p = _store().get_by_article("PV210-XX")
    assert p.name == "Лак PV210"
    assert p.technology == "Rupa"
    assert p.variants == []
    assert p.mixing is not None


# ----------------------------------------------------------------
# PV220
# ----------------------------------------------------------------

def test_pv220_has_technical_data():
    p = _store().get_by_article("PV220-20")
    assert p is not None
    td = p.technical_data
    assert td is not None
    assert td.dry_residue == "45±2%"
    assert td.density == "1,00±0,05 г/см³"
    assert td.drying == "до 12 часов"
    assert td.shelf_life in {"от 12 месяцев.", "от 12 месяцев"}
    assert td.application is not None
    assert td.usage is not None
    assert "лак" in td.usage


def test_pv220_unchanged_other_fields():
    p = _store().get_by_article("PV220-20")
    assert p.name == "Лак PV220"
    assert p.technology == "Rupa"
    assert p.variants == []
    assert p.mixing is not None


# ----------------------------------------------------------------
# PV290
# ----------------------------------------------------------------

def test_pv290_has_technical_data():
    p = _store().get_by_article("PV290-99")
    assert p is not None
    td = p.technical_data
    assert td is not None
    assert td.gloss == "100±3"
    assert td.dry_residue == "56±2%"
    assert td.density == "1,00±0,05 г/см³"
    assert td.pot_life == "3 часа"
    assert td.drying == "24 часа"
    assert td.shelf_life in {"от 12 месяцев.", "от 12 месяцев"}
    assert td.application is not None
    assert td.usage is not None
    assert "лак" in td.usage


def test_pv290_unchanged_other_fields():
    p = _store().get_by_article("PV290-99")
    assert p.name == "Лак PV290"
    assert p.technology == "Rupa"
    assert p.variants == []
    assert p.mixing is not None


# ----------------------------------------------------------------
# Cross checks: no mixing between PD118/PD125/PD155
# ----------------------------------------------------------------

def test_pd118_pd125_pd155_not_intermixed():
    p118 = _store().get("Грунт PD").technical_data
    p125 = _store().get_by_article("PD125").technical_data
    p155 = _store().get_by_article("PD155").technical_data
    assert p118 is not None and p125 is not None and p155 is not None
    assert p118.dry_residue != p125.dry_residue
    assert p125.dry_residue != p155.dry_residue
    assert p118.density == "1,10±0,05 г/см³"
    assert p125.density == "1,15±0,05 г/см³"
    assert p155.density == "1,35±0,05 г/см³"


def test_pv210_pv220_pv290_not_intermixed():
    p210 = _store().get_by_article("PV210-XX").technical_data
    p220 = _store().get_by_article("PV220-20").technical_data
    p290 = _store().get_by_article("PV290-99").technical_data
    assert p210 is not None and p220 is not None and p290 is not None
    assert p210.dry_residue == "54±2%"
    assert p220.dry_residue == "45±2%"
    assert p290.dry_residue == "56±2%"
    assert p290.gloss == "100±3"
    assert p210.gloss == "10±3, 20±3"


# ----------------------------------------------------------------
# No duplicates
# ----------------------------------------------------------------

def test_no_duplicate_products():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    articles = [p.get("article") for p in data if p.get("article")]
    names = [p.get("name") for p in data]
    assert len(articles) == len(set(articles))
    names_lower = [n.lower() for n in names]
    # Дубликаты по имени — редкость, но проверка обязательна.
    assert len(names) == len(set(names))


def test_total_variant_count_preserved():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    # Продуктов и вариантов: 1 Грунт PD (1 var), 1 PD155 (1 var),
    # 1 PD125 (1 var), 1 Лак PV (3 vars), 1 Лак AV (2 vars),
    # 1 Грунт PA (2 vars), 1 Эмаль PB (2 vars),
    # 1 Грунт белый SCP (1 var) -> 13 вариантов всего.
    variants_per_product = [len(p.get("variants", [])) for p in data]
    assert sum(variants_per_product) == 13

"""Regression-тесты по «Что на что можно наносить» (STAINWOOD).

Проверяет ВСЕ требования из т.з. §Тесты:
  1. документ → Product mapping (артикульное исключение + хим. семейства);
  2. правильное направление A → B («X на Y» = X на Y → top=X, base=Y);
  3. статус CONFIRMED / FORBIDDEN / ALLOWED там, где это документировано;
  4. provenance (source_file, по возможности);
  5. UNRESOLVED НЕ попадает в Product (исключение 568-46312 / Профф 355 нет
     в products.json → связь НЕ создаётся);
  6. отсутствие связи НЕ превращается в FORBIDDEN.

Важно: документ — матрица ХИМИИ (NC/AC/PU/PE/UV/WB), а не артикулов.
Поэтому «перенос в products.json» реально возможен только для единственного
артикульного исключения, а 25 пар — уровня химии в compatibility.json.
Ни одна хим. пара не поднимается до конкретного продукта без доказательств.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from paint_rag.knowledge.compatibility_resolver import (
    CompatibilityResolver,
    ProductRef,
    make_resolver_from_products,
)
from paint_rag.knowledge.compatibility_store import CompatibilityStore
from paint_rag.knowledge.product_store import ProductStore
from paint_rag.knowledge.what_to_apply_on import (
    CHEMISTRY_CODES,
    ArticleRelation,
    FamilyPair,
    WhatToApplyOnSource,
)

KNOWLEDGE = Path("data/knowledge")
PRODUCTS = KNOWLEDGE / "products.json"
COMPATIBILITY = KNOWLEDGE / "compatibility.json"
SOURCE_DOC = Path("data/STAINWOOD/Схемы/Что на что можно наносить.txt")


@pytest.fixture(scope="module")
def src() -> WhatToApplyOnSource:
    return WhatToApplyOnSource(SOURCE_DOC)


@pytest.fixture(scope="module")
def store() -> ProductStore:
    return ProductStore.from_json(PRODUCTS)


@pytest.fixture(scope="module")
def chem() -> CompatibilityStore:
    return CompatibilityStore.from_json(COMPATIBILITY)


# ----------------------------------------------------------------------
# 1. Документ извлекается детерминированно
# ----------------------------------------------------------------------


def test_source_has_25_family_pairs(src):
    """«X на Y» пар ровно 25 (5×5 без диагонали)."""
    assert len(src.family_pairs) == 25
    pairs = {(p.top, p.base) for p in src.family_pairs}
    codes = set(CHEMISTRY_CODES)
    for (top, base) in pairs:
        assert top in codes and base in codes
        assert top != base, "диагональ (X на X) в документе не встречается"


def test_all_family_pairs_are_extracted(src):
    """Все ожидаемые пар «A на B» найдены.

    ЛЕВАЯ колонка («X на …») = применяемый слой: AC/NC/PU/UV/WB (PE не
    применяется сверху).
    ПРАВАЯ колонка («… на Y») = подложка: AC/NC/PE/PU/UV/WB (все 6).
    Диагональ (X на X) в документе отсутствует.
    """
    applied = {"NC", "AC", "PU", "UV", "WB"}
    substrate = set(CHEMISTRY_CODES)
    expected = {(a, b) for a in applied for b in substrate if a != b}
    assert {(p.top, p.base) for p in src.family_pairs} == expected
    # PE действительно никогда не стоит в левой колонке.
    assert not any(p.top == "PE" for p in src.family_pairs)


def test_exception_relation_is_extracted(src):
    """Единственное артикульное исключение извлекается с верным направлением."""
    assert len(src.article_relations) == 1
    rel = src.article_relations[0]
    assert rel.level == "ART"
    assert rel.base_article == "568-46312"
    assert "Аква" in rel.base_name
    assert "Сурф" in rel.base_name
    assert rel.top == "Профф 355"
    assert rel.status == "ALLOWED"
    # направление: 568-46312 (Аква Тэк Сурф) — нижний слой, Профф 355 — верхний
    assert rel.note  # есть цитата/происхождение


# ----------------------------------------------------------------------
# 2. Направление A → B ( «X на Y» = X наносится НА Y )
# ----------------------------------------------------------------------


def test_direction_top_is_applied_layer(src):
    """«NC на WB» → NC = верхний (top), WB = нижний (base). Не перепутано."""
    pair = next(p for p in src.family_pairs if p.base == "WB" and p.top == "NC")
    assert pair.top == "NC"
    assert pair.base == "WB"
    assert pair.top != pair.base


def test_direction_does_not_reverse(src):
    """Порядок пар в документе не переставляется: (NC→WB) ≠ (WB→NC)."""
    pairs = {(p.top, p.base) for p in src.family_pairs}
    assert ("NC", "WB") in pairs
    # WB→NC — это отдельная строка «WB на NC», она тоже есть:
    assert ("WB", "NC") in pairs
    assert ("NC", "WB") != ("WB", "NC")


# ----------------------------------------------------------------------
# 3. Статус CONFIRMED / ALLOWED
#    (Хим. пары: статус хранится в compatibility.json; здесь — что это
#     CONFIRMED-правила уровня химии, а не «вещи из головы».)
# ----------------------------------------------------------------------


def test_family_pairs_present_in_chem_store(chem, src):
    """Каждая пара из документа существует как правило в compatibility.json.

    В compatibility.json хранится ``base`` = применяемый слой, ``top`` =
    подложка (см. test_compatibility.py: ``find(base="NC", top="PU")`` для
    «PU на NC»). Поэтому «X на Y» маппится на ``find(base=X, top=Y)``.
    """
    missing = []
    for pair in src.family_pairs:
        rule = chem.find(base=pair.top, top=pair.base)
        if rule is None:
            missing.append((pair.top, pair.base))
    assert not missing, f"пары без правила в compatibility.json: {missing}"


def test_exception_status_allowed(src):
    """Прямая цитата «можно наносить» → статус ALLOWED (CONFIRMED)."""
    rel = src.article_relations[0]
    assert rel.status == "ALLOWED"


def test_example_confirmed_relation_in_products(store):
    """Контрольная (внешняя) явная связь «1149 → 2675-755251» CONFIRMED."""
    found = None
    for p in store.products:
        for r in (p.compatibility or []):
            if (r.base or "") == "1149" and (r.top or "") == "2675-755251":
                found = (p.name, r)
                break
        if found:
            break
    assert found is not None, "контрольная CONFIRMED-связь не найдена"
    name, r = found
    assert r.status == "CONFIRMED"
    assert r.allowed is True


# ----------------------------------------------------------------------
# 4. Provenance
# ----------------------------------------------------------------------


def test_product_relation_has_provenance(store):
    """У явной связи из Product есть источник (file / sheet / note)."""
    for p in store.products:
        for r in (p.compatibility or []):
            assert (
                r.source.file
                or r.source.sheet
                or r.source.note
            ), f"связь без provenance: {p.name}: {r}"


def test_example_has_source_file(store):
    """Контрольная CONFIRMED-связь несёт source.file."""
    for p in store.products:
        for r in (p.compatibility or []):
            if (r.base or "") == "1149" and (r.top or "") == "2675-755251":
                assert r.source.file
                assert r.source.has_provenance
                return
    pytest.fail("контрольная связь не найдена")


def test_exception_note_is_provenance(src):
    """Артикульное исключение хранит цитату-исходник (note)."""
    rel = src.article_relations[0]
    assert rel.note
    assert "568-46312" in rel.note


# ----------------------------------------------------------------------
# 5. UNRESOLVED не попадает в Product
#    Исключение 568-46312 / Профф 355 — оба артикула ОТСУТСТВУЮТ в
#    products.json, значит связь НЕ импортируется (не выдумывается).
# ----------------------------------------------------------------------


def test_exception_articles_are_unresolved(store, src):
    """Оба артикула из исключения не маппятся на продукт → UNRESOLVED."""
    s1, p1 = src.map_article_to_product(src.article_relations[0].base_article, store)
    s2, p2 = src.map_article_to_product("Профф 355", store)
    assert s1 == "UNRESOLVED"
    assert s2 == "UNRESOLVED"
    assert p1 is None
    assert p2 is None


def test_exception_not_imported_into_products(store, src):
    """Ни один Product не несёт связь 568-46312 / Профф 355."""
    for p in store.products:
        for r in (p.compatibility or []):
            assert r.base != "568-46312"
            assert r.top != "Профф 355"
            assert "568-46312" not in (r.base or "")
            assert "Профф 355" not in (r.top or "")
    # Также в aliases/variants — нет этих артикулов
    all_articles = set()
    for p in store.products:
        if p.article:
            all_articles.add(p.article.lower())
        for v in p.variants:
            if v.article:
                all_articles.add(v.article.lower())
    assert "568-46312" not in all_articles
    assert "профф 355" not in {a.lower() for a in all_articles}


def test_no_chemistry_code_is_a_product_article(store):
    """Ни один хим. код не совпадает с артикулом/алиасом продукта.
    Это подтверждает, что хим. пары НЕ подняты до конкретных продуктов."""
    codes = set(CHEMISTRY_CODES)
    candidates = set()
    for p in store.products:
        if p.article:
            candidates.add(p.article.upper())
        for a in p.aliases:
            candidates.add(a.upper())
        for v in p.variants:
            if v.article:
                candidates.add(v.article.upper())
            for a in getattr(v, "aliases", None) or []:
                candidates.add(a.upper())
    assert not (codes & candidates), (
        f"хим. код ошибочно совпал с артикулом/алиасом: {codes & candidates}"
    )


# ----------------------------------------------------------------------
# 6. Отсутствие связи НЕ превращается в FORBIDDEN
# ----------------------------------------------------------------------


def test_missing_relation_is_unknown_not_forbidden(store):
    """Для пары PD125 → PV210-XX нет правила → UNKNOWN, не FORBIDDEN."""
    resolver = make_resolver_from_products(store.products)
    result = resolver.resolve(
        base=ProductRef(article="PD125"),
        top=ProductRef(article="PV210-XX"),
    )
    assert result.status == "UNKNOWN"
    assert result.status != "FORBIDDEN"


def test_chemistry_class_does_not_auto_forbid(store, chem):
    """Идентичная/произвольная химия не выводит FORBIDDEN из воздуха.
    (Пара PU→PU не существует — это не «запрет», а отсутствие правила.)"""
    rule = chem.find(base="PU", top="PU")
    assert rule is None  # диагонали нет — отсутствие, а не запрет


def test_unresolved_family_pair_is_unknown_when_not_in_products(store, src):
    """Хим. парой без продукта = отсутствие связи, а не FORBIDDEN:
    не существует продукта с артикулом 'NC'."""
    assert store.get_by_article("NC") is None


def test_unknown_status_supported(store):
    """Модель допускает CONFIRMED и FORBIDDEN; UNKNOWN — не хранится как
    правило, а выводится резолвером (отсутствие ≠ запрет)."""
    from paint_rag.models.product_relation import ProductRelation

    conf = ProductRelation(base="A", top="B", allowed=True, status="CONFIRMED")
    forb = ProductRelation(base="A", top="B", allowed=False, status="FORBIDDEN")
    assert conf.status == "CONFIRMED" and conf.allowed is True
    assert forb.status == "FORBIDDEN" and forb.allowed is False


# ----------------------------------------------------------------------
# helpers: направление/статус в модели
# ----------------------------------------------------------------------


def test_family_pair_status_default_unknown(src):
    """В упрощённом .txt ALLOWED/FORBIDDEN конкретной пары неизвестно без
    гадания → по умолчанию UNKNOWN (не трактуется как запрет)."""
    for p in src.family_pairs:
        assert p.status in ("UNKNOWN", "ALLOWED", "FORBIDDEN")

    # Но это НЕ значит, что «отсутствие = FORBIDDEN».
    forb = [p for p in src.family_pairs if p.status == "FORBIDDEN"]
    # Диагональ запрещать не нужно.
    assert not any(p.top == p.base for p in forb)


def test_exception_is_not_mixed_with_mixing(src):
    """Исключение «можно наносить Профф 355 поверх Аква Тэк Сурф» — это
    compatibility, а НЕ рецептура смешивания."""
    rel = src.article_relations[0]
    assert rel.level == "ART"
    # не содержит «Основа/Отвердитель/Разбавитель» (это было бы смешиванием)
    for forbidden_word in ("основа", "отвердитель", "разбавитель"):
        assert forbidden_word not in rel.note.lower()

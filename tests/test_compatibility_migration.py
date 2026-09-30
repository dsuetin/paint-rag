"""Тесты миграции совместимости (задача 3).

Ключевые гарантии:
* Product.compatibility — источник истины для подтверждённых связей;
* отсутствие связи = UNKNOWN (НЕ FORBIDDEN);
* legacy матрица NC/AC/PU/PE/UV/WB НЕ становится CONFIRMED;
* совместимость НЕ выводится из химического класса;
* runtime не зависит от data/knowledge/compatibility.json как источника.
"""
import json
from pathlib import Path

import pytest

from paint_rag.knowledge.compatibility_resolver import (
    CompatibilityResolver,
    ProductRef,
    build_structured_result,
    make_resolver_from_products,
)
from paint_rag.knowledge.compatibility_store import CompatibilityStore
from paint_rag.knowledge.product_store import ProductStore
from paint_rag.models.product_relation import ProductRelation

DATA = Path("data/knowledge")
PRODUCTS = DATA / "products.json"
COMPATIBILITY = DATA / "compatibility.json"
RELATIONS = DATA / "product_relations.json"


@pytest.fixture(scope="module")
def store() -> ProductStore:
    return ProductStore.from_json(PRODUCTS)


def ddur_base(product_store: ProductStore):
    """Помощник: вернуть продукт Д-дур грунт 1149 из store."""
    product = product_store.find("1149")
    assert product, "продукт 1149 не найден"
    return product[0]


# ----------------------------------------------------------------------
# 1. Загрузка compatibility в Product
# ----------------------------------------------------------------------


def test_product_model_has_compatibility_field(store):
    """У продукта «Грунт Д-ДУР Плюс Белый» есть compatibility со связью
    1149 → 2675-755251 (CONFIRMED)."""
    product = ddur_base(store)
    assert len(product.compatibility) >= 1
    relation = product.compatibility[0]
    assert relation.top == "2675-755251"
    assert relation.status == "CONFIRMED"
    assert relation.allowed is True


def test_compatibility_relation_has_full_provenance(store):
    """Каждая перенесённая связь несёт source с file/note."""
    product = ddur_base(store)
    relation = product.compatibility[0]
    assert relation.source.file == (
        "Полиуретан/D-DUR/Эмаль Д-Дур база 01 полумат.pdf"
    )
    assert relation.source.note
    assert relation.source.has_provenance


# ----------------------------------------------------------------------
# 2. Legacy codes: расшифровка кодов NC/AC/PU/PE/UV/WB
# ----------------------------------------------------------------------


def test_legacy_codes_are_chemistry_not_products(store):
    """Коды NC/AC/PU/PE/UV/WB — это НАЗВАНИЯ ХИМИЧЕСКИХ СИСТЕМ, а не
    артикулы. Ни один продукт в products.json не имеет article из этого
    набора; соответствия к конкретным продуктам не существует."""
    legacy = json.loads(COMPATIBILITY.read_text(encoding="utf-8"))
    codes = {r["base"].upper() for r in legacy} | {
        r["top"].upper() for r in legacy
    }
    expected = {"NC", "AC", "PU", "PE", "UV", "WB"}
    assert codes == expected

    all_articles = set()
    for p in store.products:
        if p.article:
            all_articles.add(p.article)
    for v in (pv for p in store.products for pv in p.variants):
        if v.article:
            all_articles.add(v.article)
    for code in codes:
        assert code not in all_articles, (
            f"legacy код {code} ошибочно совпал с артикулом продукта"
        )


def test_legacy_relation_has_no_provenance():
    """Legacy-матрица в compatibility.json не содержит source —
    это НЕ подтверждённые связи."""
    legacy = json.loads(COMPATIBILITY.read_text(encoding="utf-8"))
    for rule in legacy:
        assert "source" not in rule or not rule["source"]
        assert "file" not in rule
        assert "page" not in rule


# ----------------------------------------------------------------------
# 3. Product → Variant / article
# ----------------------------------------------------------------------


def test_variant_article_resolution(store):
    """get_variant_by_article находит продукт с вариантами по артикулу
    варианта; продуктов с вариантами есть в store."""
    with_variants = [
        p for p in store.products if p.variants
    ]
    assert with_variants, "ожидались продукты с вариантами"
    sample = with_variants[0]
    article = sample.variants[0].article
    if article:
        found = store.get_variant_by_article(article)
        assert found is not None
        product, variant = found
        assert product.name == sample.name


# ----------------------------------------------------------------------
# 4-6. CONFIRMED / FORBIDDEN / UNKNOWN через resolver
# ----------------------------------------------------------------------


def test_confirmed_ddur_primer_on_enamel(store):
    """CONFIRMED: Д-дур грунт 1149 под эмаль 2675-755251."""
    resolver = make_resolver_from_products(store.products)
    result = resolver.resolve(
        base=ProductRef(article="1149"),
        top=ProductRef(article="2675-755251"),
    )
    assert result.status == "CONFIRMED"
    assert result.findings
    assert result.findings[0].source is not None
    assert result.findings[0].source.get("file") == (
        "Полиуретан/D-DUR/Эмаль Д-Дур база 01 полумат.pdf"
    )


def test_missing_relation_is_unknown_not_forbidden(store):
    """КРИТИЧЕСКИЙ тест: отсутствие связи ≠ FORBIDDEN.

    Пара (PD125 → PV210-XX): ни в Product.compatibility, ни в
    product_relations.json, ни в legacy не описана. Должно быть
    UNKNOWN, а не FORBIDDEN.
    """
    resolver = make_resolver_from_products(store.products)
    result = resolver.resolve(
        base=ProductRef(article="PD125"),
        top=ProductRef(article="PV210-XX"),
    )
    assert result.status == "UNKNOWN"
    assert result.to_prompt_dict()["status"] == "UNKNOWN"


def test_legacy_only_pair_is_not_confirmed(store):
    """Легаси-пары (например, NC → PU allowed=True) НЕ становятся
    CONFIRMED: у них нет первичного источника.

    Даже если legacy-матрица (connects NC→PU as allowed) загружена в
    CompatibilityStore, связь «PD125 под PV210-XX» не подтверждена,
    потому что ни Product.compatibility, ни product_relations.py не
    содержат её.
    """
    from paint_rag.knowledge.compatibility_store import CompatibilityStore
    from paint_rag.knowledge.relation_store import RelationStore

    chemistry = CompatibilityStore.from_json(COMPATIBILITY)
    relations = RelationStore.from_json(RELATIONS)
    resolver = CompatibilityResolver(
        chemistry=chemistry,
        relations=relations,
        products=store.products,
    )
    result = resolver.resolve(
        base=ProductRef(article="PD125"),
        top=ProductRef(article="PV210-XX"),
    )
    # Ни одна явная связь между PD125 и PV210-XX не существует
    # (нет ни в Product.compatibility, ни в product_relations.json,
    #  ни в legacy хим. матрице на уровне артикулов).
    assert result.status == "UNKNOWN"




def test_forbidden_status_stored_in_product():
    """FORBIDDEN сохраняется в Product.compatibility как status=FORBIDDEN
    (модель допускает оба статуса)."""
    rel = ProductRelation(
        base="A",
        top="B",
        allowed=False,
        status="FORBIDDEN",
        reason="test",
    )
    assert rel.status == "FORBIDDEN"
    assert rel.allowed is False


# ----------------------------------------------------------------------
# 8. Отсутствие ложной совместимости
# ----------------------------------------------------------------------


def test_chemistry_class_does_not_imply_compatibility(store):
    """Оба продукта полиуретановые ≠ совместимы: совместимость НЕ
    выводится из химического класса (ТЗ §8)."""
    resolver = make_resolver_from_products(store.products)
    result = resolver.resolve(
        base=ProductRef(article="PV220-20", chemistry="PU"),
        top=ProductRef(article="PA334-9016", chemistry="PU"),
    )
    # Не CONFIRMED по умолчанию из-за идентичной химии.
    confirmed_from_chemistry = any(
        f.status == "CONFIRMED" and f.legacy is True
        for f in (result.findings or [])
    )
    assert not confirmed_from_chemistry


def test_no_false_compatibility_for_unrelated_products(store):
    """Не связанные продукты → нет подтверждённых связей."""
    resolver = make_resolver_from_products(store.products)
    result = resolver.resolve(
        base=ProductRef(article="WT 420"),
        top=ProductRef(article="PD155"),
    )
    assert result.status in ("UNKNOWN", "FORBIDDEN")
    if result.findings:
        # Если есть findings — только явные.
        for f in result.findings:
            assert f.status in ("CONFIRMED", "FORBIDDEN", "UNKNOWN")


# ----------------------------------------------------------------------
# 9. Отсутствие зависимости runtime от compatibility.json
# ----------------------------------------------------------------------


def test_resolver_works_without_compatibility_json(tmp_path, store):
    """Runtime: resolver использует Product.compatibility, не legacy JSON.
    Убираем legacy-файл — resolver продолжает работать."""
    bak = COMPATIBILITY.with_name(COMPATIBILITY.name + ".hidden")
    compat_backup = COMPATIBILITY.read_text(encoding="utf-8")
    try:
        COMPATIBILITY.rename(bak)
        resolver = make_resolver_from_products(store.products)
        result = resolver.resolve(
            base=ProductRef(article="1149"),
            top=ProductRef(article="2675-755251"),
        )
        assert result.status == "CONFIRMED"
        assert result.findings and result.findings[0].source is not None
    finally:
        bak.rename(COMPATIBILITY)
        assert COMPATIBILITY.read_text(encoding="utf-8") == compat_backup


def test_make_resolver_defaults_to_no_legacy_sources(store):
    """make_resolver_from_products по умолчанию НЕ подключает legacy
    compatibility.json и product_relations.json — только Product."""
    resolver = make_resolver_from_products(store.products)
    assert len(resolver.chemistry.rules) == 0
    assert len(resolver.relations.relations) == 0
    assert len(resolver.products) == len(store.products)


# ----------------------------------------------------------------------
# 10. Provenance
# ----------------------------------------------------------------------


def test_provenance_present_in_product_compatibility(store):
    """У каждой связи в Product.compatibility есть source.file или note."""
    found_any = False
    for product in store.products:
        for relation in product.compatibility:
            found_any = True
            assert (
                relation.source.file
                or relation.source.note
                or relation.source.sheet
            ), f"sвязь без provenance: {relation}"
    assert found_any, "не найдено ни одной перенесённой связи"


def test_build_structured_result_from_product(store):
    """build_structured_result отдаёт CONFIRMED из Product, не из legacy."""
    resolver = make_resolver_from_products(store.products)
    results = build_structured_result(
        resolver=resolver,
        base_ref=ProductRef(article="1149"),
        top_ref=ProductRef(article="2675-755251"),
    )
    assert results
    assert results[0].status == "CONFIRMED"
    assert any(
        f.get("source", {}).get("file")
        == "Полиуретан/D-DUR/Эмаль Д-Дур база 01 полумат.pdf"
        for f in (results[0].model_dump().get("findings") or [])
    )


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _relations_store():
    from paint_rag.knowledge.relation_store import RelationStore
    return RelationStore.from_json(RELATIONS)

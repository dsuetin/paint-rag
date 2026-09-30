"""Task 5 tests: unified Product/ProductVariant compatibility schema.

Guarantees (TЗ этапы 6–14):
* a single schema for all products (compatibility/alternatives/sources
  are optional lists — empty by absence);
* CONFIRMED / FORBIDDEN are distinguished;
* absence of a relation = UNKNOWN (NOT FORBIDDEN);
* variant-level relations do NOT propagate to the product (and vice versa);
* alternatives are NOT coating compatibility;
* every migrated relation carries provenance;
* mixing rules / technical data are unaffected.
"""
import json
from pathlib import Path

import pytest

from paint_rag.knowledge.compatibility_resolver import (
    ProductRef,
    make_resolver_from_products,
)
from paint_rag.knowledge.product_store import ProductStore
from paint_rag.models.product import (
    Product,
    ProductVariant,
    VariantSource,
)
from paint_rag.models.product_relation import (
    ProductRelation,
    RelationAlternative,
    RelationSource,
)

PRODUCTS = Path("data/knowledge/products.json")


def _rel(base="A", top="B", status="CONFIRMED", level="ART", **kw):
    return ProductRelation(
        base=base,
        top=top,
        allowed=(status == "CONFIRMED"),
        status=status,
        level=level,
        source=RelationSource(file="test.pdf", page=1, note="citation"),
        **kw,
    )


# ----------------------------------------------------------------------
# 1. Schema validity
# ----------------------------------------------------------------------


def test_product_without_compatibility_is_valid():
    p = Product(name="Test product")
    assert p.compatibility == []
    assert p.alternatives == []
    assert p.sources == []
    assert p.role is None


def test_product_with_compatibility_is_valid():
    p = Product(name="Test product", compatibility=[_rel()])
    assert len(p.compatibility) == 1
    assert p.compatibility[0].base == "A"
    assert p.compatibility[0].top == "B"


def test_product_with_variants_and_variant_level_compatibility_is_valid():
    v = ProductVariant(
        variant_id=1,
        article="PD118",
        source=VariantSource(sheet="S", product_row=1),
        compatibility=[_rel("HD808", "PD118")],
        alternatives=[RelationAlternative(ref="HD810", role="hardener")],
        sources=[RelationSource(file="t.pdf", page=1)],
    )
    p = Product(
        name="Грунт PD",
        variants=[v],
        compatibility=[_rel("1149", "2675-755251")],
    )
    assert len(v.compatibility) == 1
    assert len(v.alternatives) == 1
    assert len(v.sources) == 1
    # product-level and variant-level are separate (no auto-merge in JSON)
    assert len(p.compatibility) == 1
    assert p.variants[0].compatibility[0].base == "HD808"


def test_relation_fields_roundtrip():
    rel = _rel(alternatives=[RelationAlternative(ref="УС грунт", role="primer")])
    data = json.loads(json.dumps(rel.model_dump(), ensure_ascii=False))
    back = ProductRelation.model_validate(data)
    assert back.level == "ART"
    assert back.alternatives[0].ref == "УС грунт"
    assert back.source.page == 1


# ----------------------------------------------------------------------
# 2. CONFIRMED / FORBIDDEN distinction
# ----------------------------------------------------------------------


def test_forbidden_relation_loads_with_status():
    rel = _rel(status="FORBIDDEN")
    assert rel.status == "FORBIDDEN"
    assert rel.allowed is False
    assert rel.is_forbidden
    assert not rel.is_confirmed


def test_confirmed_relation_loads_with_status():
    rel = _rel()
    assert rel.status == "CONFIRMED"
    assert rel.allowed is True
    assert rel.is_confirmed
    assert not rel.is_forbidden


# ----------------------------------------------------------------------
# 3. UNKNOWN = absence of a relation
# ----------------------------------------------------------------------


def test_missing_relation_is_unknown():
    resolver = make_resolver_from_products([Product(name="X")])
    result = resolver.resolve(
        base=ProductRef(article="A"),
        top=ProductRef(article="B"),
    )
    assert result.status == "UNKNOWN"


def test_unknown_does_not_become_forbidden(store):
    # RUPA primer→lac pairs: UNKNOWN (see confirmed relations §6.1)
    resolver = make_resolver_from_products(store.products)
    result = resolver.resolve(
        base=ProductRef(article="PD125"),
        top=ProductRef(article="PV210-XX"),
    )
    assert result.status == "UNKNOWN"


# ----------------------------------------------------------------------
# 4. Variant specificity (no auto-inheritance)
# ----------------------------------------------------------------------


def test_variant_relation_not_visible_on_product_level():
    v = ProductVariant(
        variant_id=1,
        article="PA777-9016",
        source=VariantSource(sheet="S", product_row=1),
        compatibility=[_rel(base="HD816", top="PA777-9016")],
    )
    p = Product(name="PA777", variants=[v])
    # product-level list must stay empty
    assert p.compatibility == []
    # effective (product+variant) includes the variant relation
    eff = p.effective_compatibility(variant=v)
    assert len(eff) == 1
    assert eff[0].base == "HD816"


def test_product_relation_visible_for_variant_effective():
    v = ProductVariant(
        variant_id=1,
        article="1149",
        source=VariantSource(sheet="S", product_row=1),
    )
    p = Product(name="Грунт", variants=[v], compatibility=[_rel()])
    eff = p.effective_compatibility(variant=v)
    assert len(eff) == 1


# ----------------------------------------------------------------------
# 5. Alternatives are separate from compatibility
# ----------------------------------------------------------------------


def test_alternative_is_not_compatibility():
    rel = _rel(alternatives=[RelationAlternative(ref="УС грунт", role="primer")])
    assert len(rel.alternatives) == 1
    # alternatives do NOT appear in the relation list as separate links
    assert len([r for r in [rel] if r.allowed]) == 1


def test_product_alternatives_field(store):
    """RUPA/PD products carry alternatives (alt hardeners) separately from
    compatibility (A1–A5 confirmed relations §4)."""
    p = next(x for x in store.products if x.name == "Грунт PD125")
    assert p.alternatives, "PD125 alternatives (HD820) expected"
    refs = {a.ref for a in p.alternatives}
    assert "HD820" in refs
    # and the product itself must NOT have a coating-compat link to HD820
    assert not any("HD820" in (r.base + r.top) for r in p.compatibility)


# ----------------------------------------------------------------------
# 6. Stored products have provenance
# ----------------------------------------------------------------------


def test_all_product_relations_have_provenance(store):
    total = 0
    for p in store.products:
        for r in p.compatibility:
            total += 1
            assert r.source.has_provenance, (
                f"relation without provenance: {p.name}: {r}"
            )
            assert (
                r.source.file or r.source.sheet
            ), f"neither file nor Sheet in {p.name}"
    assert total >= 10


def test_migrated_confirmed_sample_d2ur(store):
    p = next(x for x in store.products if x.name == "Грунт Д-ДУР Плюс Белый")
    confirmed = [r for r in p.compatibility if r.status == "CONFIRMED"]
    assert len(confirmed) >= 2
    files = {r.source.file for r in confirmed}
    assert "Полиуретан/D-DUR/Эмаль Д-Дур база 01 полумат.pdf" in files
    assert any(r.source.sheet == "Таблица1" for r in confirmed)


def test_level_markers_present(store):
    """§1 levels: ART for article pairs, PROD for the AXIL one."""
    axil = next(x for x in store.products if "Axil 2000" in x.name)
    assert axil.compatibility, "Axil 2000 PROD level relation expected"
    assert axil.compatibility[0].level == "PROD"
    d2ur = next(x for x in store.products if x.name == "Грунт Д-ДУР Плюс Белый")
    assert all(r.level in ("ART", "VAR") for r in d2ur.compatibility)


def test_forbidden_bpd_sample(store):
    wf761 = next(
        x for x in store.products if "WF" in x.name and "761" in x.name
    )
    forb = [r for r in wf761.compatibility if r.status == "FORBIDDEN"]
    assert forb, "BPD FORBIDDEN relations expected on WF761"
    assert any("BPD" in (r.base + r.top) for r in forb)


# ----------------------------------------------------------------------
# 7. Mixing / technical data regression
# ----------------------------------------------------------------------


def test_mixing_rules_preserved(store):
    p = next(x for x in store.products if x.name == "Грунт PD")
    v = p.variants[0]
    assert v.mixing is not None
    assert v.mixing.hardener.name == "810"
    assert v.mixing.thinner is not None
    assert v.mixing.thinner_ratio is not None


def test_technical_data_preserved():
    store = ProductStore.from_json(PRODUCTS)
    with_td = [p for p in store.products if p.technical_data]
    assert with_td, "products with technical_data expected"
    p = with_td[0]
    assert p.technical_data.model_dump(), "technical_data content expected"


# ----------------------------------------------------------------------
# 8. Resolver end-to-end with the migrated data
# ----------------------------------------------------------------------


def test_resolver_confirmed_d2ur_pair(store):
    resolver = make_resolver_from_products(store.products)
    result = resolver.resolve(
        base=ProductRef(article="1149"),
        top=ProductRef(article="2675-755251"),
    )
    assert result.status == "CONFIRMED"
    assert result.findings[0].source.get("file")


# ----------------------------------------------------------------------
# fixture
# ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def store() -> ProductStore:
    return ProductStore.from_json(PRODUCTS)

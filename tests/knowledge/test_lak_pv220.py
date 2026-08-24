import json
from pathlib import Path

from paint_rag.knowledge.product_store import (
    ProductStore,
)


PRODUCTS = Path(
    "data/knowledge/products.json"
)


def _store() -> ProductStore:
    return ProductStore.from_json(PRODUCTS)


def _get_pv220():

    product = _store().get_by_article(
        "PV220-20"
    )

    assert product is not None

    return product


def test_lak_pv220_product_exists():

    product = _get_pv220()

    assert (
        product.name
        == "Лак PV220"
    )


def test_lak_pv220_article_and_technology():

    product = _get_pv220()

    assert product.article == "PV220-20"

    assert product.technology == "Rupa"


def test_lak_pv220_aliases():

    product = _get_pv220()

    assert "PV220" in product.aliases

    assert (
        "Универсальный прозрачный полиуретановый 2K лак"
        in product.aliases
    )


def test_lak_pv220_consumption():

    product = _get_pv220()

    assert product.consumption_min == 120.0

    assert product.consumption_max == 140.0

    assert (
        product.consumption_unit
        == "g_per_m2"
    )


def test_lak_pv220_max_layers():

    product = _get_pv220()

    assert product.max_layers == 2


def test_lak_pv220_mixing():

    product = _get_pv220()

    mixing = product.mixing

    assert mixing is not None

    assert mixing.base_percent == 100.0

    assert (
        mixing.hardener.name
        == "HD820"
    )

    assert mixing.hardener.percent == 50.0

    assert (
        mixing.thinner_ratio.min
        == 15.0
    )

    assert (
        mixing.thinner_ratio.max
        == 30.0
    )


def test_lak_pv220_no_variants():

    product = _get_pv220()

    assert product.variants == []


def test_lak_pv220_source_points_to_pdf():

    data = json.loads(
        PRODUCTS.read_text(
            encoding="utf-8"
        )
    )

    (product,) = [
        item
        for item in data
        if item["name"]
        == "Лак PV220"
    ]

    assert (
        product["source"]["file"]
        == "Rupa_PV220_20_Прозрачный_ПУ_лак_универсальный.pdf"
    )

    assert product["source"]["page"] == 1


def test_lak_pv220_found_by_article_alias_and_find():

    store = _store()

    assert (
        store.get_by_article(
            "PV220-20"
        ).name
        == "Лак PV220"
    )

    assert (
        store.get(
            "PV220"
        ).name
        == "Лак PV220"
    )

    assert [
        product.name
        for product in store.find(
            "PV220"
        )
    ] == [
        "Лак PV220"
    ]


def test_lak_pv_unchanged():

    store = _store()

    product = store.get(
        "Лак PV"
    )

    assert product is not None

    prices = [
        variant.unit_price
        for variant in product.variants
    ]

    assert prices == [
        220.0,
        290.0,
        210.0,
    ]

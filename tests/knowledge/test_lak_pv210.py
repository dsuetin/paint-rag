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


def _get_pv210() -> ProductStore:
    product = _store().get_by_article(
        "PV210-XX"
    )

    assert product is not None

    return product


def test_lak_pv210_product_exists():

    product = _get_pv210()

    assert (
        product.name
        == "Лак PV210"
    )


def test_lak_pv210_article_and_technology():

    product = _get_pv210()

    assert product.article == "PV210-XX"

    assert product.technology == "Rupa"


def test_lak_pv210_aliases():

    product = _get_pv210()

    assert "PV210" in product.aliases

    assert (
        "Высокопрочный прозрачный полиуретановый 2K лак"
        in product.aliases
    )


def test_lak_pv210_consumption():

    product = _get_pv210()

    assert product.consumption_min == 120.0

    assert product.consumption_max == 160.0

    assert (
        product.consumption_unit
        == "g_per_m2"
    )


def test_lak_pv210_mixing():

    product = _get_pv210()

    mixing = product.mixing

    assert mixing is not None

    assert mixing.base_percent == 100.0

    assert (
        mixing.hardener.name
        == "HD870"
    )

    assert mixing.hardener.percent == 100.0

    assert (
        mixing.thinner_ratio.min
        == 15.0
    )

    assert (
        mixing.thinner_ratio.max
        == 30.0
    )


def test_lak_pv210_no_variants():

    product = _get_pv210()

    assert product.variants == []


def test_lak_pv210_source_points_to_pdf():

    data = json.loads(
        PRODUCTS.read_text(
            encoding="utf-8"
        )
    )

    (product,) = [
        item
        for item in data
        if item["name"]
        == "Лак PV210"
    ]

    assert (
        product["source"]["file"]
        == "Rupa_PV210_XX_Прозрачный_ПУ_лак_высокопрочный_1.pdf"
    )

    assert product["source"]["page"] == 1


def test_lak_pv210_found_by_alias_and_find():

    store = _store()

    assert (
        store.get(
            "PV210"
        ).name
        == "Лак PV210"
    )

    assert [
        product.name
        for product in store.find(
            "PV210"
        )
    ] == [
        "Лак PV210"
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

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


def test_pd155_product_exists():

    store = _store()

    product = store.get_by_article(
        "PD155"
    )

    assert product is not None

    assert product.article == "PD155"


def test_pd155_name_and_technology():

    store = _store()

    product = store.get_by_article(
        "PD155"
    )

    assert product is not None

    assert (
        product.name
        == "Грунт PD155 изолятор для МДФ"
    )

    assert product.technology == "Rupa"


def test_pd155_alias():

    store = _store()

    product = store.get_by_article(
        "PD155"
    )

    assert product is not None

    assert "PD155" in product.aliases


def test_pd155_mixing_hd820_and_ratio():

    store = _store()

    product = store.get_by_article(
        "PD155"
    )

    assert product is not None

    assert product.mixing is not None

    assert product.mixing.base_percent == 100.0

    assert (
        product.mixing.hardener.name
        == "HD820"
    )

    assert (
        product.mixing.hardener.percent
        == 50.0
    )

    assert product.mixing.thinner_ratio is not None

    assert (
        product.mixing.thinner_ratio.min
        == 15.0
    )

    assert (
        product.mixing.thinner_ratio.max
        == 30.0
    )


def test_pd155_max_layers():

    store = _store()

    product = store.get_by_article(
        "PD155"
    )

    assert product is not None

    assert product.max_layers == 2


def test_pd155_variant_article_and_price():

    store = _store()

    (product, variant) = (
        store.get_variant_by_article(
            "PD155"
        )
    )

    assert product.article == "PD155"

    assert variant.article == "PD155"

    assert variant.price == 155.0


def test_pd155_variant_source_points_to_pdf():

    data = json.loads(
        PRODUCTS.read_text(
            encoding="utf-8"
        )
    )

    (product,) = [
        item
        for item in data
        if item["name"]
        == "Грунт PD155 изолятор для МДФ"
    ]

    (variant,) = [
        variant
        for variant in product["variants"]
        if variant["price"] == 155.0
    ]

    assert (
        variant["source"]["file"]
        == "Rupa_PD155_Прозрачный_ПУ_грунт_изолятор_для_МДФ.pdf"
    )

    assert variant["source"]["page"] == 1


def test_grunt_pd_no_longer_has_155():

    store = _store()

    grunt_pd = store.get(
        "Грунт PD"
    )

    assert grunt_pd is not None

    prices = [
        variant.unit_price
        for variant in grunt_pd.variants
    ]

    assert 155.0 not in prices

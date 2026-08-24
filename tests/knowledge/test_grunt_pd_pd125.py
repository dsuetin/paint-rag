from pathlib import Path

from paint_rag.knowledge.product_store import (
    ProductStore,
)


PRODUCTS = Path(
    "data/knowledge/products.json"
)


def test_grunt_pd_found():

    store = ProductStore.from_json(
        PRODUCTS
    )

    product = store.get(
        "Грунт PD"
    )

    assert product is not None


def test_grunt_pd125_product_exists():

    store = ProductStore.from_json(
        PRODUCTS
    )

    product = store.get_by_article(
        "PD125"
    )

    assert product is not None

    assert (
        product.name
        == "Грунт PD125"
    )

    (variant,) = [
        variant
        for variant in product.variants
        if variant.unit_price == 125.0
    ]

    assert variant.article == "PD125"


def test_grunt_pd125_alias_pd125():

    store = ProductStore.from_json(
        PRODUCTS
    )

    product = store.get_by_article(
        "PD125"
    )

    assert product is not None

    assert "PD125" in product.aliases

    assert (
        "Прозрачный полиуретановый 2K грунт"
        in product.aliases
    )


def test_grunt_pd125_mixing():

    store = ProductStore.from_json(
        PRODUCTS
    )

    product = store.get_by_article(
        "PD125"
    )

    assert product is not None

    (variant,) = [
        variant
        for variant in product.variants
        if variant.unit_price == 125.0
    ]

    mixing = variant.mixing

    assert mixing is not None

    assert mixing.base_percent == 100.0

    assert (
        mixing.hardener.name
        == "HD810"
    )

    assert (
        mixing.hardener.percent
        == 50.0
    )

    assert (
        mixing.thinner_ratio.min
        == 15.0
    )

    assert (
        mixing.thinner_ratio.max
        == 30.0
    )

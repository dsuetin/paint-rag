from pathlib import Path

from paint_rag.knowledge.product_store import (
    ProductStore,
)


PRODUCTS = Path(
    "data/knowledge/products.json"
)


def test_load_products():

    store = ProductStore.from_json(
        PRODUCTS
    )

    assert len(store.all()) > 0


def test_find_ground_pd():

    store = ProductStore.from_json(
        PRODUCTS
    )

    products = store.find(
        "Грунт PD"
    )

    assert len(products) >= 1

    product = products[0]

    assert product.name == "Грунт PD"

    assert len(product.variants) == 3


def test_ground_pd_variants():

    store = ProductStore.from_json(
        PRODUCTS
    )

    product = store.get(
        "Грунт PD"
    )

    assert product is not None

    assert len(product.variants) == 3

    prices = [
        variant.unit_price
        for variant in product.variants
    ]

    assert prices == [
        155.0,
        125.0,
        118.0,
    ]
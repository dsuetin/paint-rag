from pathlib import Path

from paint_rag.knowledge.product_store import (
    ProductStore,
)


PRODUCTS = Path(
    "data/knowledge/products.json"
)


def test_lac_d_dur_by_article():

    store = ProductStore.from_json(
        PRODUCTS
    )

    product = store.get_by_article(
        "2575-001251"
    )

    assert product is not None

    assert product.name == "Лак Д-ДУР"

    assert product.article == "2575-001251"

    assert (
        product.mixing.hardener.name
        == "1.871.1085 (Д-Дур)"
    )

    assert (
        product.mixing.hardener.percent
        == 30
    )

    assert (
        product.mixing.thinner.name
        == "800-00218 или DSI"
    )

    assert (
        product.mixing.thinner.percent
        == 30
    )

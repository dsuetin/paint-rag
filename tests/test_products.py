from pathlib import Path

from paint_rag.knowledge.product_store import (
    ProductStore,
)


DATA = Path("data/knowledge/products.json")


def test_find_pa334():

    store = ProductStore.from_json(DATA)

    products = store.find("PA334-9016")

    assert len(products) == 1

    product = products[0]

    assert product.article == "PA334-9016"
    assert product.consumption_min == 120
    assert product.consumption_max == 140
    assert product.max_layers == 2
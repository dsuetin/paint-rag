from pathlib import Path

from paint_rag.knowledge.product_store import (
    ProductStore,
)


DATA = Path("data/knowledge/products.json")


def test_pa334_mixing():

    store = ProductStore.from_json(DATA)

    product = store.get_by_article(
        "PA334-9016"
    )

    assert product is not None
    assert product.mixing is not None

    assert product.mixing.hardener.name == "HD816"

    assert (
        product.mixing.hardener_ratio.min
        == 33
    )

    assert (
        product.mixing.thinner_ratio.min
        == 15
    )

    assert (
        product.mixing.thinner_ratio.max
        == 30
    )

    
import json
from pathlib import Path

from paint_rag.knowledge.product_store import (
    ProductStore,
)


PRODUCTS = Path(
    "data/knowledge/products.json"
)


def _load_store():
    return ProductStore.from_json(PRODUCTS)


def test_grunt_pd_exists():

    store = _load_store()

    product = store.get(
        "Грунт PD"
    )

    assert product is not None


def test_pd118_variant_exists():

    store = _load_store()

    product = store.get(
        "Грунт PD"
    )

    assert product is not None

    (variant,) = [
        variant
        for variant in product.variants
        if variant.unit_price == 118.0
    ]

    assert variant.variant_id == 3


def test_pd118_variant_article():

    store = _load_store()

    product = store.get(
        "Грунт PD"
    )

    assert product is not None

    (variant,) = [
        variant
        for variant in product.variants
        if variant.unit_price == 118.0
    ]

    assert variant.article == "PD118"


def test_product_alias_pd118():

    store = _load_store()

    product = store.get(
        "Грунт PD"
    )

    assert product is not None

    assert "PD118" in product.aliases

    assert (
        "Прозрачный полиуретановый 2K грунт Super"
        in product.aliases
    )

    assert (
        "2K грунт сери Super"
        in product.aliases
    )


def test_pd118_source_file_and_page():

    data = json.loads(
        PRODUCTS.read_text(
            encoding="utf-8"
        )
    )

    (product,) = [
        item
        for item in data
        if item["name"] == "Грунт PD"
    ]

    (variant,) = [
        variant
        for variant in product["variants"]
        if variant["price"] == 118.0
    ]

    assert (
        variant["source"]["file"]
        == "Rupa_PD118_Прозрачный_ПУ_грунт_серии_Super.pdf"
    )

    assert variant["source"]["page"] == 1


def test_pd118_mixing_unchanged():

    store = _load_store()

    product = store.get(
        "Грунт PD"
    )

    assert product is not None

    (variant,) = [
        variant
        for variant in product.variants
        if variant.unit_price == 118.0
    ]

    mixing = variant.mixing

    assert mixing is not None

    assert mixing.base_percent == 100.0

    assert mixing.hardener.name == "810"

    assert mixing.hardener.percent == 50.0

    assert mixing.thinner.percent == 30.0

    assert mixing.total_ratio == 1.8

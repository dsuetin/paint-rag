from pathlib import Path

from paint_rag.knowledge.product_store import (
    ProductStore,
)


PRODUCTS = Path(
    "data/knowledge/products.json"
)


def _store() -> ProductStore:
    return ProductStore.from_json(PRODUCTS)


def test_get_variant_by_article_pd118():

    store = _store()

    result = store.get_variant_by_article(
        "PD118"
    )

    assert result is not None

    product, variant = result

    assert product.name == "Грунт PD"

    assert variant.unit_price == 118.0

    assert variant.article == "PD118"


def test_get_variant_by_article_case_and_spaces():

    store = _store()

    (product, variant) = (
        store.get_variant_by_article(
            "  pd118 "
        )
    )

    assert variant.unit_price == 118.0


def test_get_variant_by_article_missing():

    store = _store()

    assert (
        store.get_variant_by_article(
            "UNKNOWN-ARTICLE"
        )
        is None
    )


def test_get_variant_by_article_product_level_fallback():
    """
    Продукт «Лак Д-ДУР» имеет article=2575-001251
    и пустые variants. Фallback по product.article
    требует непустых variants, поэтому вернёт None —
    это ожидаемое поведение для продукта без вариантов.
    """

    store = _store()

    assert (
        store.get_variant_by_article(
            "2575-001251"
        )
        is None
    )


def test_get_variant_by_article_empty():

    store = _store()

    assert store.get_variant_by_article("") is None

    assert store.get_variant_by_article("   ") is None

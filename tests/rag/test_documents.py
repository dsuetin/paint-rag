from pathlib import Path

from paint_rag.knowledge.product_store import (
    ProductStore,
)
from paint_rag.rag.documents import (
    product_to_documents,
)


DATA = Path(
    "data/knowledge/products.json"
)


def test_product_to_documents():

    store = ProductStore.from_json(DATA)

    product = store.get_by_article(
        "PA334-9016"
    )

    assert product is not None

    documents = product_to_documents(
        product
    )

    assert len(documents) == 1

    document = documents[0]

    assert document.product == product.name

    assert document.variant_id == 1

    assert "PA334-9016" in document.text

    assert "HD816" in document.text

    assert "33%" in document.text

    assert "15%" in document.text

    assert "30%" in document.text


def test_document_to_chunks():
    store = ProductStore.from_json(DATA)

    product = store.get_by_article("PA334-9016")
    assert product is not None

    documents = product_to_documents(product)

    chunks = document_to_chunks(documents[0])

    assert len(chunks) == 1

    chunk = chunks[0]

    assert chunk.text == documents[0].text
    assert chunk.product == "БЕЛЫЙ ПОЛИУРЕТАНОВЫЙ 2K ГРУНТ"
    assert chunk.article == "PA334-9016"
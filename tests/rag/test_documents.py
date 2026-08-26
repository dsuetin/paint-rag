from pathlib import Path

from paint_rag.knowledge.product_store import (
    ProductStore,
)
from paint_rag.rag.documents import (
    product_to_documents,
    document_to_chunks
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

    assert len(chunks) >= 1

    first = chunks[0]

    assert first.product == "БЕЛЫЙ ПОЛИУРЕТАНОВЫЙ 2K ГРУНТ"
    assert first.article == "PA334-9016"
    assert first.chunk_id == 0

    # Все чанки несут article и product (не теряется при chunking).
    for ch in chunks:
        assert ch.product == "БЕЛЫЙ ПОЛИУРЕТАНОВЫЙ 2K ГРУНТ"
        assert ch.article == "PA334-9016"

    # Технический данных попадает в текст документа.
    td = product.technical_data
    if td is not None:
        assert (
            "Технические характеристики" in documents[0].text
        )


def test_document_carries_technical_data():
    store = ProductStore.from_json(DATA)

    product = store.get_by_article("PA334-9016")
    assert product is not None
    assert product.technical_data is not None

    docs = product_to_documents(product)
    doc = docs[0]
    assert doc.metadata.get("technical_data") is not None
    assert "Сухой остаток" in doc.text

    chunks = doc.chunks
    assert chunks
    for ch in chunks:
        assert ch.technical_data is not None
        assert ch.technical_data == doc.metadata["technical_data"]


def test_document_carries_source_metadata():
    store = ProductStore.from_json(DATA)

    product = store.get_by_article("PA334-9016")
    assert product is not None

    docs = product_to_documents(product)
    doc = docs[0]

    # metadata.source не теряется при конвертации Product -> Document.
    source = doc.metadata.get("source")
    assert source is not None
    assert "row" in source

    for ch in doc.chunks:
        assert ch.source is not None
        assert "row" in ch.source
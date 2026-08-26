"""Task 13 — Source tracking regression: file/page should survive
JSON -> Product -> Document -> Chunk without loss."""
import json
from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.models.product import Product
from paint_rag.rag.documents import product_to_documents, document_to_chunks


DATA = Path("data/knowledge/products.json")


def test_source_file_and_page_from_json():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    found = [p for p in data if p.get("article") == "PV210-XX"]
    (raw,) = found
    assert "file" in raw.get("source", {})
    assert raw["source"]["page"] == 1


def test_source_round_trips_through_pydantic():
    store = ProductStore.from_json(DATA)
    p = store.get_by_article("PV210-XX")
    assert p is not None
    assert p.source is not None
    assert p.source.file
    assert p.source.page == 1
    # dump and back — should preserve.
    d = p.model_dump(mode="json")
    p2 = Product.model_validate(d)
    assert p2.source.file == p.source.file
    assert p2.source.page == p.source.page


def test_product_to_document_preserves_source():
    store = ProductStore.from_json(DATA)
    p = store.get_by_article("PV210-XX")
    assert p is not None
    docs = product_to_documents(p)
    doc = docs[0]
    assert doc.metadata.get("source", {}).get("file") == p.source.file
    assert doc.metadata["source"]["page"] == 1


def test_document_to_chunk_preserves_source():
    store = ProductStore.from_json(DATA)
    p = store.get_by_article("PV210-XX")
    assert p is not None
    docs = product_to_documents(p)
    chunks = document_to_chunks(docs[0])
    assert chunks
    for ch in chunks:
        assert ch.source is not None
        assert ch.source.get("file") == p.source.file
        assert ch.source.get("page") == 1


def test_no_product_creates_new_products():
    store = ProductStore.from_json(DATA)
    before = len(store.products)
    assert before == 40


def test_no_new_variants():
    store = ProductStore.from_json(DATA)
    total = sum(len(p.variants) for p in store.products)
    # 13 вариантов по данным products.json — backfill не добавил.
    assert total == 13

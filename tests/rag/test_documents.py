from pathlib import Path

from paint_rag.knowledge.product_store import (
    ProductStore,
)
from paint_rag.models.product import (
    Product,
    ProductVariant,
    VariantSource,
)
from paint_rag.models.product_relation import (
    ProductRelation,
    RelationSource,
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


# ---------------------------------------------------------------------------
# Compatibility / alternatives / provenance (Task 6, Phase 2-4)
# ---------------------------------------------------------------------------


def test_document_carries_compatibility_relations():
    """Product с compatibility -> Document: все relation,
    status, target, source присутствуют и во всем, и во всех chunks."""
    store = ProductStore.from_json(DATA)

    product = store.get("Эмаль Д-ДУР-01")
    assert product is not None
    assert product.compatibility, "fixture должен иметь compatibility"

    docs = product_to_documents(product)
    doc = docs[0]

    meta_compat = doc.metadata.get("compatibility")
    assert meta_compat is not None
    assert len(meta_compat) == len(product.effective_compatibility(None))

    statuses = {c["status"] for c in meta_compat}
    assert "CONFIRMED" in statuses
    assert "FORBIDDEN" in statuses

    for c in meta_compat:
        assert c["base"]
        assert c["top"]
        assert c["source"]["file"]

    # Провенанс relation не потерян.
    sources = doc.metadata.get("relation_sources")
    assert sources
    assert any(s.get("file") for s in sources)

    # Текст документа содержит явный блок совместимости.
    assert "Совместимость" in doc.text
    assert "CONFIRMED" in doc.text
    assert "FORBIDDEN" in doc.text
    assert "1149" in doc.text
    assert "2675-755251" in doc.text

    # Chunking не удаляет compatibility: блок разбит между чанками,
    # но в сумме по чанкам присутствуют обе строки; metadata — в каждом.
    chunks = doc.chunks
    assert chunks
    joined = "".join(ch.text for ch in chunks)
    assert "Совместимость" in joined
    assert "CONFIRMED" in joined
    assert "FORBIDDEN" in joined
    for ch in chunks:
        assert ch.compatibility == doc.metadata["compatibility"]
        assert ch.relation_sources == doc.metadata["relation_sources"]


def test_document_preserves_undefined_compatibility_as_unknown():
    """Product без compatibility: документ создаётся корректно,
    а text явно отмечает отсутствие подтверждённых связей (UNKNOWN)."""
    store = ProductStore.from_json(DATA)

    product = store.get("Лак PV210")
    assert product is not None
    assert not product.compatibility

    docs = product_to_documents(product)
    doc = docs[0]

    assert doc.text  # документ не пустой
    assert "документированных подтверждённых связей не найдено" in doc.text
    assert doc.metadata.get("compatibility") is None

    for ch in doc.chunks:
        assert ch.compatibility is None
    assert any("не найдено" in ch.text for ch in doc.chunks)


def test_document_carries_alternatives_and_distinction_from_compatibility():
    """Альтернативы попадают в document/chunks;
    текст явно разделяет их от coating-совместимости."""
    store = ProductStore.from_json(DATA)

    product = store.get("Эмаль Д-ДУР-01")
    assert product is not None
    assert product.alternatives

    docs = product_to_documents(product)
    doc = docs[0]

    meta_alts = doc.metadata.get("alternatives")
    assert meta_alts
    refs = {a["ref"] for a in meta_alts}
    assert "УС грунт" in refs
    assert "DSI" in refs

    assert "Альтернативы компонентов" in doc.text
    assert "УС грунт" in doc.text
    assert "DSI" in doc.text

    assert any("Альтернативы компонентов" in ch.text for ch in doc.chunks)
    for ch in doc.chunks:
        assert ch.alternatives == doc.metadata["alternatives"]


def test_variant_level_compatibility_visible_for_that_variant_only():
    """Variant-level relations видны только в документе своего варианта."""
    variant_rel = ProductRelation(
        base="V-100",
        top="T-200",
        allowed=True,
        status="CONFIRMED",
        source=RelationSource(file="x.pdf", page=7),
    )
    product = Product(
        name="Test Var Product",
        article="TV-1",
        variants=[
            ProductVariant(
                variant_id=1,
                article="TV-1-A",
                compatibility=[variant_rel],
                source=VariantSource(sheet="S", product_row=1),
            ),
            ProductVariant(
                variant_id=2,
                article="TV-1-B",
                source=VariantSource(sheet="S", product_row=2),
            ),
        ],
    )

    docs = product_to_documents(product)
    assert len(docs) == 2

    doc_a, doc_b = docs[0], docs[1]
    assert "T-200" in doc_a.text
    assert any(c["base"] == "V-100" for c in doc_a.metadata["compatibility"])

    # Вариант без relations: только UNKNOWN-маркер.
    assert doc_b.metadata.get("compatibility") is None
    assert "документированных подтверждённых связей не найдено" in doc_b.text
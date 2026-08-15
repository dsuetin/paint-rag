from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.rag.documents import product_to_documents
from paint_rag.rag.retriever import Retriever


DATA = Path(
    "data/knowledge/products.json"
)


def build_retriever() -> Retriever:
    store = ProductStore.from_json(DATA)

    product = store.get_by_article(
        "PA334-9016"
    )

    assert product is not None

    documents = product_to_documents(
        product
    )

    return Retriever.from_documents(
        documents
    )


def test_find_hardener():
    retriever = build_retriever()

    results = retriever.search(
        "какой отвердитель у PA334-9016?"
    )

    assert len(results) > 0

    text = "\n".join(
        result.text
        for result in results
    )

    assert "HD816" in text
    assert "33%" in text


def test_find_thinner():
    retriever = build_retriever()

    results = retriever.search(
        "сколько разбавителя добавлять в PA334-9016?"
    )

    assert len(results) > 0

    text = "\n".join(
        result.text
        for result in results
    )

    assert "15%" in text
    assert "30%" in text


def test_find_consumption():
    retriever = build_retriever()

    results = retriever.search(
        "какой расход грунта PA334-9016?"
    )

    assert len(results) > 0

    text = "\n".join(
        result.text
        for result in results
    )

    assert "120" in text
    assert "140" in text
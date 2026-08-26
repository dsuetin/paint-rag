"""Task 12 — Retriever integration test.

Two products A/B share technology=Rupa but have different
articles. Verifies AND semantics of article filter and that
a technology-only filter returns both.
"""
from paint_rag.rag.documents import Chunk
from paint_rag.rag.retriever import Retriever
from paint_rag.rag.vector_store import VectorStore


class _FakeModel:
    def embed_query(self, text: str) -> list[float]:
        return [1.0]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]


def _chunk(article):
    return Chunk(
        id=f"article:{article}:0",
        text=f"Продукт {article}",
        product=f"Профиль {article}",
        variant_id=1,
        article=article,
        chunk_id=0,
        technology="Rupa",
    )


def _store_with_both() -> VectorStore:
    vs = VectorStore()
    a = _chunk("PA777-9016")
    b = _chunk("PV210")
    vs.add([a, b], [[1.0], [1.0]])
    return vs


def _retriever(vs: VectorStore) -> Retriever:
    return Retriever(vector_store=vs, embedding_model=_FakeModel())


def test_article_filter_isolated():
    """Поиск по article=PA777-9016 не вернёт PV210."""
    r = _retriever(_store_with_both())
    results = r.search(
        "что-то важное",
        article="PA777-9016",
        top_k=10,
    )
    articles = {x.chunk.article for x in results}
    assert articles == {"PA777-9016"}
    assert "PV210" not in articles


def test_article_filter_reverse():
    r = _retriever(_store_with_both())
    results = r.search(
        "что-то важное",
        article="PV210",
        top_k=10,
    )
    articles = {x.chunk.article for x in results}
    assert articles == {"PV210"}


def test_technology_filter_returns_both():
    """Поиск по technology=Rupa может вернуть и PA777-9016, и PV210."""
    r = _retriever(_store_with_both())
    results = r.search(
        "что-то важное",
        technology="Rupa",
        top_k=10,
    )
    articles = {x.chunk.article for x in results}
    assert articles == {"PA777-9016", "PV210"}


def test_article_plus_technology_AND():
    """AND: article + technology. Оба присутствуют — вернётся
    только chunk с этим article."""
    r = _retriever(_store_with_both())
    results = r.search(
        "что-то важное",
        article="PV210",
        technology="Rupa",
        top_k=10,
    )
    articles = {x.chunk.article for x in results}
    assert articles == {"PV210"}

    # Невалидный tech-фильтр отсекает оба.
    none_results = r.search(
        "что-то важное",
        article="PV210",
        technology="Oswald",
        top_k=10,
    )
    assert none_results == []


def test_product_filter():
    r = _retriever(_store_with_both())
    results = r.search(
        "что-то важное",
        product=f"Профиль PV210",
        top_k=10,
    )
    articles = {x.chunk.article for x in results}
    assert articles == {"PV210"}


def test_filter_case_insensitive():
    r = _retriever(_store_with_both())
    by_article = {
        x.chunk.article
        for x in r.search("q", article="pv210", top_k=10)
    }
    assert by_article == {"PV210"}
    by_tech = {
        x.chunk.article
        for x in r.search("q", technology="rUpA", top_k=10)
    }
    assert by_tech == {"PA777-9016", "PV210"}

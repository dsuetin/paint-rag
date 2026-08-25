from paint_rag.rag.documents import Chunk
from paint_rag.rag.retriever import Retriever
from paint_rag.rag.vector_store import VectorStore


class FakeEmbeddingModel:

    def __init__(self):
        self.vectors = {
            "отвердитель": [1.0, 0.0, 0.0],
            "разбавитель": [0.0, 1.0, 0.0],
            "расход": [0.0, 0.0, 1.0],
        }

    def embed_query(
        self,
        text: str,
    ) -> list[float]:

        text = text.lower()

        for key, vector in self.vectors.items():
            if key in text:
                return vector

        return [0.0, 0.0, 0.0]

    def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        return [
            self.embed_query(text)
            for text in texts
        ]


def make_chunk(
    chunk_id: int,
    text: str,
) -> Chunk:

    return Chunk(
        id=f"chunk-{chunk_id}",
        text=text,
        product="Грунт PA334",
        variant_id=1,
        article="PA334-9016",
        chunk_id=chunk_id,
    )


def test_retriever():

    store = VectorStore()

    chunks = [
        make_chunk(
            0,
            "Отвердитель HD816 33%",
        ),
        make_chunk(
            1,
            "Разбавитель 15-30%",
        ),
        make_chunk(
            2,
            "Расход 120-140 г/м2",
        ),
    ]

    vectors = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]

    store.add(
        chunks,
        vectors,
    )

    retriever = Retriever(
        vector_store=store,
        embedding_model=FakeEmbeddingModel(),
    )

    results = retriever.search(
        "какой отвердитель?",
        top_k=1,
    )

    assert len(results) == 1

    result = results[0]

    assert result.chunk.article == "PA334-9016"
    assert "HD816" in result.chunk.text
    assert result.score == 1.0


def _make_store_with_metadata():

    store = VectorStore()

    chunks = [
        Chunk(
            id="c-0",
            text="PA334-9016 100% HD816 33%",
            product="Белый полиуретановый 2K грунт",
            variant_id=1,
            article="PA334-9016",
            chunk_id=0,
            technology="Rupa",
        ),
        Chunk(
            id="c-1",
            text="PD125 100% HD810 50%",
            product="Грунт PD125",
            variant_id=1,
            article="PD125",
            chunk_id=1,
            technology="Rupa",
        ),
        Chunk(
            id="c-2",
            text="PA334-9016 альтернативный",
            product="Белый полиуретановый 2K грунт",
            variant_id=2,
            article="PA334-9016",
            chunk_id=2,
            technology="AkzoNobel",
        ),
    ]

    vectors = [[1.0, 0.0, 0.0]] * 3

    store.add(chunks, vectors)

    return store


def test_retriever_without_filters_unchanged():

    store = _make_store_with_metadata()

    retriever = Retriever(
        vector_store=store,
        embedding_model=FakeEmbeddingModel(),
    )

    results = retriever.search("какой отвердитель?", top_k=3)

    assert len(results) == 3


def test_retriever_filter_by_article():

    store = _make_store_with_metadata()

    retriever = Retriever(
        vector_store=store,
        embedding_model=FakeEmbeddingModel(),
    )

    results = retriever.search(
        "отвердитель",
        top_k=3,
        article="PA334-9016",
    )

    assert len(results) == 2

    for r in results:
        assert r.chunk.article == "PA334-9016"


def test_retriever_filter_by_product():

    store = _make_store_with_metadata()

    retriever = Retriever(
        vector_store=store,
        embedding_model=FakeEmbeddingModel(),
    )

    results = retriever.search(
        "отвердитель",
        top_k=3,
        product="Грунт PD125",
    )

    assert len(results) == 1
    assert results[0].chunk.product == "Грунт PD125"


def test_retriever_filter_by_technology():

    store = _make_store_with_metadata()

    retriever = Retriever(
        vector_store=store,
        embedding_model=FakeEmbeddingModel(),
    )

    results = retriever.search(
        "отвердитель",
        top_k=3,
        technology="AkzoNobel",
    )

    assert len(results) == 1
    assert results[0].chunk.technology == "AkzoNobel"


def test_retriever_multiple_filters_and():

    store = _make_store_with_metadata()

    retriever = Retriever(
        vector_store=store,
        embedding_model=FakeEmbeddingModel(),
    )

    results = retriever.search(
        "отвердитель",
        top_k=3,
        article="PA334-9016",
        technology="Rupa",
    )

    assert len(results) == 1
    assert (
        results[0].chunk.article == "PA334-9016"
    )
    assert (
        results[0].chunk.technology
        == "Rupa"
    )


def test_retriever_filters_case_insensitive():

    store = _make_store_with_metadata()

    retriever = Retriever(
        vector_store=store,
        embedding_model=FakeEmbeddingModel(),
    )

    results = retriever.search(
        "отвердитель",
        top_k=3,
        article="pa334-9016",
        product="белый полиуретановый 2k грунт",
    )

    assert len(results) == 2


def test_retriever_filters_ignores_surrounding_spaces():

    store = _make_store_with_metadata()

    retriever = Retriever(
        vector_store=store,
        embedding_model=FakeEmbeddingModel(),
    )

    results = retriever.search(
        "отвердитель",
        top_k=3,
        article="  PA334-9016  ",
    )

    assert len(results) == 2


def test_retriever_unknown_filter_returns_empty():

    store = _make_store_with_metadata()

    retriever = Retriever(
        vector_store=store,
        embedding_model=FakeEmbeddingModel(),
    )

    results = retriever.search(
        "отвердитель",
        top_k=3,
        article="UNKNOWN-ARTICLE",
    )

    assert results == []
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
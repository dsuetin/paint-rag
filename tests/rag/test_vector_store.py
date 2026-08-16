from paint_rag.rag.documents import Chunk
from paint_rag.rag.vector_store import VectorStore


def make_chunk(
    chunk_id: int,
    text: str,
) -> Chunk:

    return Chunk(
        id=f"chunk-{chunk_id}",
        text=text,
        product="Product",
        variant_id=1,
        article="TEST",
        chunk_id=chunk_id,
    )


def test_vector_store_search():

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

    results = store.search(
        [1.0, 0.0, 0.0],
        top_k=1,
    )

    assert len(results) == 1

    chunk, score = results[0]

    assert chunk.text == "Отвердитель HD816 33%"
    assert score == 1.0
from paint_rag.models.document import Chunk
from paint_rag.rag.chunk_store import ChunkStore


def make_chunk(
    chunk_id: int,
    article: str | None = None,
    product: str = "Грунт PA334",
) -> Chunk:
    return Chunk(
        id=f"{article or 'x'}:{1}:{chunk_id}",
        text=f"chunk {chunk_id}",
        product=product,
        variant_id=1,
        article=article,
        chunk_id=chunk_id,
    )


def test_init_with_chunks():
    chunks = [make_chunk(0, "PA334-9016"), make_chunk(1, "PA334-9016")]
    store = ChunkStore(chunks)
    assert store.all() == chunks


def test_default_init_empty():
    store = ChunkStore()
    assert store.all() == []


def test_add():
    store = ChunkStore()
    chunk = make_chunk(0)
    store.add(chunk)
    assert store.all() == [chunk]


def test_add_many():
    store = ChunkStore()
    chunks = [make_chunk(0, "PA334-9016"), make_chunk(1, "PA334-9016")]
    store.add_many(chunks)
    assert store.all() == chunks


def test_get_found():
    store = ChunkStore([make_chunk(0), make_chunk(5)])
    assert store.get(5) is not None
    assert store.get(5).chunk_id == 5


def test_get_not_found():
    store = ChunkStore([make_chunk(0)])
    assert store.get(42) is None


def test_find_by_article():
    store = ChunkStore([
        make_chunk(0, "PA334-9016"),
        make_chunk(1, "PA334-9016"),
        make_chunk(2, "PD210-1"),
        make_chunk(3, None),
    ])
    result = store.find_by_article("PA334-9016")
    assert [c.chunk_id for c in result] == [0, 1]


def test_find_by_article_case_and_spaces():
    store = ChunkStore([make_chunk(0, "PA334-9016")])
    assert store.find_by_article(" pa334-9016 ") == store.all()


def test_find_by_article_not_found():
    store = ChunkStore([make_chunk(0, "PA334-9016")])
    assert store.find_by_article("UNKNOWN") == []


def test_find_by_product():
    store = ChunkStore([
        make_chunk(0, "PA334-9016", product="Грунт PA334"),
        make_chunk(1, "PA334-9016", product="Грунт PA334"),
        make_chunk(2, "PD210-1", product="Грунт PD"),
    ])
    result = store.find_by_product("Грунт PA334")
    assert [c.chunk_id for c in result] == [0, 1]


def test_find_by_product_case_insensitive():
    store = ChunkStore([make_chunk(0, product="Грунт PA334")])
    assert len(store.find_by_product("грунт pa334")) == 1


def test_mutating_init_list_does_not_affect_store():
    chunks = [make_chunk(0)]
    store = ChunkStore(chunks)
    chunks.append(make_chunk(1))
    assert len(store.all()) == 1

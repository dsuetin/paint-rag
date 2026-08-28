from paint_rag.models.document import Chunk
from paint_rag.rag.chunk_store import ChunkStore
from paint_rag.rag.embedding_indexer import EmbeddingIndexer
from paint_rag.rag.embedding_provider import (
    EmbeddingProvider,
    FakeEmbeddingProvider,
)
from paint_rag.rag.embedding_store import EmbeddingStore


def make_chunk(index: int, text: str) -> Chunk:
    return Chunk(
        id=f"PA334-9016:1:{index}",
        text=text,
        product="Грунт PA334",
        variant_id=1,
        article="PA334-9016",
        chunk_id=index,
    )


def test_single_chunk_gets_embedding():
    chunk_store = ChunkStore([make_chunk(0, "Грунт PA334")])
    provider = FakeEmbeddingProvider(8)
    embedding_store = EmbeddingStore()
    indexer = EmbeddingIndexer(chunk_store, provider, embedding_store)

    indexer.index_chunk(chunk_store.all()[0])

    assert len(embedding_store) == 1


def test_embedding_saved_with_correct_chunk_id():
    chunk = make_chunk(3, "Текст чанка")
    chunk_store = ChunkStore([chunk])
    provider = FakeEmbeddingProvider(8)
    embedding_store = EmbeddingStore()
    indexer = EmbeddingIndexer(chunk_store, provider, embedding_store)

    indexer.index_chunk(chunk)

    expected = provider.embed(chunk.text)
    assert embedding_store.get(chunk.id) == expected


def test_index_all_multiple_chunks():
    chunks = [
        make_chunk(0, "Первый текст"),
        make_chunk(1, "Второй текст"),
        make_chunk(2, "Третий текст"),
    ]
    chunk_store = ChunkStore(chunks)
    provider = FakeEmbeddingProvider(8)
    embedding_store = EmbeddingStore()
    indexer = EmbeddingIndexer(chunk_store, provider, embedding_store)

    indexer.index_all()

    assert len(embedding_store) == 3
    for chunk in chunks:
        assert embedding_store.get(chunk.id) == provider.embed(chunk.text)


def test_empty_chunk_store_no_error():
    chunk_store = ChunkStore()
    provider = FakeEmbeddingProvider(8)
    embedding_store = EmbeddingStore()
    indexer = EmbeddingIndexer(chunk_store, provider, embedding_store)

    indexer.index_all()

    assert len(embedding_store) == 0


def test_reindex_updates_embedding():
    class FixedProvider(EmbeddingProvider):
        def __init__(self, value: float) -> None:
            self.value = value

        def embed(self, text: str) -> list[float]:
            return [self.value, self.value]

    chunk = make_chunk(0, "Текст")
    chunk_store = ChunkStore([chunk])
    first = FixedProvider(1.0)
    embedding_store = EmbeddingStore()
    indexer = EmbeddingIndexer(chunk_store, first, embedding_store)

    indexer.index_all()
    assert embedding_store.get(chunk.id) == [1.0, 1.0]

    indexer.provider = FixedProvider(5.0)
    indexer.index_all()
    assert embedding_store.get(chunk.id) == [5.0, 5.0]
    assert len(embedding_store) == 1


# --- batch indexing -------------------------------------------------


class _BatchProvider(EmbeddingProvider):
    """Provider с batch-методом; считает количество вызовов."""

    def __init__(self) -> None:
        self.embed_calls = 0
        self.embed_batch_calls = 0

    def embed(self, text: str) -> list[float]:
        self.embed_calls += 1
        return [len(text), 0.0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.embed_batch_calls += 1
        return [[len(t), i] for i, t in enumerate(texts)]


def test_index_many_uses_batch_when_available():
    chunks = [make_chunk(0, "A"), make_chunk(1, "AB"), make_chunk(2, "ABC")]
    store = ChunkStore(chunks)
    provider = _BatchProvider()
    es = EmbeddingStore()
    indexer = EmbeddingIndexer(store, provider, es)

    calls = indexer.index_all()

    assert len(es) == 3
    assert provider.embed_batch_calls == 1
    assert provider.embed_calls == 0
    assert calls == 1
    # порядок сохранён
    assert es.get("PA334-9016:1:2")[1] == 2.0
    assert es.get("PA334-9016:1:0")[1] == 0.0


def test_index_many_fallback_without_batch():
    chunks = [make_chunk(0, "A"), make_chunk(1, "AB")]
    store = ChunkStore(chunks)
    provider = FakeEmbeddingProvider(8)
    es = EmbeddingStore()
    indexer = EmbeddingIndexer(store, provider, es)

    calls = indexer.index_all()

    assert len(es) == 2
    assert calls == 2  # по одному вызову embed на chunk

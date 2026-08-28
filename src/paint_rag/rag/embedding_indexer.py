from paint_rag.models.document import Chunk
from paint_rag.rag.chunk_store import ChunkStore
from paint_rag.rag.embedding_provider import EmbeddingProvider
from paint_rag.rag.embedding_store import EmbeddingStore


class EmbeddingIndexer:
    """Индексирует chunks: text -> embedding.

    Поддерживает batch embedding: если у провайдера есть метод
    ``embed_batch(texts)`` — используется один запрос на весь набор;
    иначе — побайтовый fallback ``embed(text)``. Сохраняет обратную
    совместимость: ``index_chunk`` / ``index_all`` работают как прежде.
    """

    def __init__(
        self,
        chunk_store: ChunkStore,
        provider: EmbeddingProvider,
        embedding_store: EmbeddingStore,
    ) -> None:
        self.chunk_store = chunk_store
        self.provider = provider
        self.embedding_store = embedding_store
        # Количество эмбеддингов, сгенерированных за одно batch-вызов.
        self._last_batch_calls = 0

    def index_chunk(self, chunk: Chunk) -> None:
        embedding = self.provider.embed(chunk.text)
        self.embedding_store.add(chunk.id, embedding)

    def index_many(
        self, chunks: list[Chunk]
    ) -> int:
        """Возвращает количество эмбеддинг-вызовов (для метрик)."""
        if not chunks:
            return 0
        embed_batch = getattr(self.provider, "embed_batch", None)
        if callable(embed_batch):
            vectors = embed_batch([chunk.text for chunk in chunks])
            for chunk, vector in zip(chunks, vectors):
                self.embedding_store.add(chunk.id, vector)
            return 1
        for chunk in chunks:
            self.index_chunk(chunk)
        return len(chunks)

    def index_all(self) -> int:
        self._last_batch_calls = self.index_many(self.chunk_store.all())
        return self._last_batch_calls

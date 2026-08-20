from paint_rag.models.document import Chunk
from paint_rag.rag.chunk_store import ChunkStore
from paint_rag.rag.embedding_provider import EmbeddingProvider
from paint_rag.rag.embedding_store import EmbeddingStore


class EmbeddingIndexer:

    def __init__(
        self,
        chunk_store: ChunkStore,
        provider: EmbeddingProvider,
        embedding_store: EmbeddingStore,
    ) -> None:
        self.chunk_store = chunk_store
        self.provider = provider
        self.embedding_store = embedding_store

    def index_chunk(self, chunk: Chunk) -> None:
        embedding = self.provider.embed(chunk.text)
        self.embedding_store.add(chunk.id, embedding)

    def index_all(self) -> None:
        for chunk in self.chunk_store.all():
            self.index_chunk(chunk)

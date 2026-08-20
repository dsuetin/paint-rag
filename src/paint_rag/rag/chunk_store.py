from paint_rag.models.document import Chunk


class ChunkStore:

    def __init__(
        self,
        chunks: list[Chunk] | None = None,
    ) -> None:
        self._chunks: list[Chunk] = list(chunks or [])

    def add(self, chunk: Chunk) -> None:
        self._chunks.append(chunk)

    def add_many(self, chunks: list[Chunk]) -> None:
        self._chunks.extend(chunks)

    def get(
        self,
        chunk_id: int,
    ) -> Chunk | None:
        for chunk in self._chunks:
            if chunk.chunk_id == chunk_id:
                return chunk
        return None

    def all(self) -> list[Chunk]:
        return list(self._chunks)

    def find_by_article(self, article: str) -> list[Chunk]:
        article = article.lower().strip()
        return [
            chunk
            for chunk in self._chunks
            if chunk.article
            and chunk.article.lower() == article
        ]

    def find_by_product(self, product: str) -> list[Chunk]:
        product = product.lower().strip()
        return [
            chunk
            for chunk in self._chunks
            if chunk.product.lower() == product
        ]

class EmbeddingStore:

    def __init__(
        self,
        embeddings: dict[str, list[float]] | None = None,
    ) -> None:
        self._embeddings: dict[str, list[float]] = dict(embeddings or {})

    def add(
        self,
        chunk_id: str,
        embedding: list[float],
    ) -> None:
        self._embeddings[chunk_id] = embedding

    def get(
        self,
        chunk_id: str,
    ) -> list[float] | None:
        return self._embeddings.get(chunk_id)

    def all(self) -> dict[str, list[float]]:
        return dict(self._embeddings)

    def __len__(self) -> int:
        return len(self._embeddings)

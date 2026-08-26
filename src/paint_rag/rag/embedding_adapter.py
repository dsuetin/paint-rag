"""Адаптеры между двумя параллельными реализациями эмбеддингов:

- Protocol ``EmbeddingModel`` (``embeddings.py``): метод ``embed_query`` /
  batch ``embed`` — используется ``VectorStore`` и ``Retriever``;
- ABC ``EmbeddingProvider`` (``embedding_provider.py``): метод ``embed`` —
  используется ``EmbeddingIndexer`` / ``EmbeddingStore``.

Объединение без большого rewrite: адаптеры позволяют использовать
любую реализацию там, где ожидается другая.
"""
from paint_rag.rag.embedding_provider import EmbeddingProvider


class ProviderAsModel:
    """Окутывает ``EmbeddingProvider`` (ABC) так, чтобы он удовлетворял
    Protocol :class:`paint_rag.rag.embeddings.EmbeddingModel`
    (методы ``embed_query`` и batch ``embed``)."""

    def __init__(self, provider: EmbeddingProvider) -> None:
        self._provider = provider

    def embed_query(self, text: str) -> list[float]:
        return self._provider.embed(text)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._provider.embed(t) for t in texts]

    @property
    def dimension(self) -> int | None:
        return getattr(self._provider, "dimension", None)


class ModelAsProvider(EmbeddingProvider):
    """Окутывает объект-модель (Protocol ``EmbeddingModel``) так, чтобы
    он удовлетворял ABC :class:`EmbeddingProvider` (метод ``embed``)."""

    def __init__(self, model) -> None:
        self._model = model

    def embed(self, text: str) -> list[float]:
        if hasattr(self._model, "embed_query"):
            return self._model.embed_query(text)
        return self._model.embed([text])[0]

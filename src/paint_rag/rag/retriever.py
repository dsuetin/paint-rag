from pydantic import BaseModel

from paint_rag.rag.documents import Chunk
from paint_rag.rag.embeddings import EmbeddingModel
from paint_rag.rag.vector_store import VectorStore


class RetrievedChunk(BaseModel):
    chunk: Chunk
    score: float


class Retriever:

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_model: EmbeddingModel,
    ):
        self.vector_store = vector_store
        self.embedding_model = embedding_model

    def search(
        self,
        query: str,
        top_k: int = 5,
        article: str | None = None,
        product: str | None = None,
        technology: str | None = None,
    ) -> list[RetrievedChunk]:

        query_vector = (
            self.embedding_model.embed_query(
                query
            )
        )

        matches = self.vector_store.search(
            query_vector,
            top_k=top_k,
        )

        results = [
            (chunk, score)
            for chunk, score in matches
            if self._matches_filters(
                chunk=chunk,
                article=article,
                product=product,
                technology=technology,
            )
        ]

        return [
            RetrievedChunk(
                chunk=chunk,
                score=score,
            )
            for chunk, score in results
        ]

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().lower()

    @classmethod
    def _field_matches(
        cls,
        expected: str | None,
        actual: str | None,
    ) -> bool:

        if expected is None:
            return True

        expected = cls._normalize(expected)

        if not expected:
            return True

        return (
            actual is not None
            and cls._normalize(actual) == expected
        )

    @classmethod
    def _matches_filters(
        cls,
        *,
        chunk: Chunk,
        article: str | None = None,
        product: str | None = None,
        technology: str | None = None,
    ) -> bool:

        return (
            cls._field_matches(article, chunk.article)
            and cls._field_matches(product, chunk.product)
            and cls._field_matches(
                technology,
                chunk.technology,
            )
        )
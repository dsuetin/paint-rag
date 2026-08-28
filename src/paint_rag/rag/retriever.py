from pydantic import BaseModel

from paint_rag.rag.documents import Chunk
from paint_rag.rag.embeddings import EmbeddingModel
from paint_rag.rag.vector_store import VectorStore


class RetrievedChunk(BaseModel):
    chunk: Chunk
    score: float


# При активных metadata-фильтрах расширяем набор кандидатов в разы,
# чтобы «поиск по article=X» гарантированно находил chunk,
# даже если его семантический ранг выше ``top_k``. Без фильтров
# фактор не применяется — top_k остаётся точным.
_FILTER_CANDIDATE_FACTOR = 8


class Retriever:

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_model: EmbeddingModel,
    ):
        self.vector_store = vector_store
        self.embedding_model = embedding_model

    def search_hybrid(
        self,
        query: str,
        top_k: int = 5,
        article: str | None = None,
        product: str | None = None,
        technology: str | None = None,
        *,
        semantic_weight: float = 1.0,
        lexical_weight: float = 1.0,
    ) -> list[RetrievedChunk]:
        """Hybrid retrieval (semantic + lexical, weighted-sum fusion).

        Backward-compatible addition — ``search`` остаётся без изменений.
        """
        from paint_rag.rag.hybrid_retrieval import hybrid_search

        return hybrid_search(
            self.vector_store,
            self.embedding_model,
            query,
            article=article,
            product=product,
            technology=technology,
            top_k=top_k,
            semantic_weight=semantic_weight,
            lexical_weight=lexical_weight,
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        article: str | None = None,
        product: str | None = None,
        technology: str | None = None,
    ) -> list[RetrievedChunk]:
        """Semantic search + optional metadata filters (AND-semantics).

        Важно: ``top_k`` — количество **отфильтрованных** результатов
        (не кандидатов). Без фильтров — это же количество кандидатов.
        При активных фильтрах расширяем кандидатов (``_FILTER_CANDIDATE_FACTOR``),
        чтобы «поиск по article=PV220-20» гарантированно находил chunk,
        даже если его семантический ранг выше ``top_k``.
        """
        query_vector = (
            self.embedding_model.embed_query(
                query
            )
        )

        has_filter = (
            article is not None
            or product is not None
            or technology is not None
        )
        candidate_k = (
            top_k * _FILTER_CANDIDATE_FACTOR if has_filter else top_k
        )

        matches = self.vector_store.search(
            query_vector,
            top_k=candidate_k,
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
            for chunk, score in results[:top_k]
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
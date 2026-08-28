"""Hybrid retrieval: semantic (cosine) + lexical (keyword) + weighted fusion.

Подход:

1. **Semantic** — существующий :meth:`VectorStore.search` (cosine similarity).
2. **Lexical** — доля токенов запроса, найденных в chunk-тексте/имени/артикуле
   (0.0..1.0).
3. **Fusion** — нормализованная взвешенная сумма:
   ``score = semantic_weight * sem_norm + lexical_weight * lex``,
   где ``sem_norm = (cosine + 1) / 2`` (маппинг [-1, 1] -> [0, 1]).

Минус RRF — при weight = 0 он всё равно использует ранг, а ранг определяется
устойчивой сортировкой (порядок входа). Взвешенная сумма чётче: weight = 0
полностью исключает компоненту из расчёта.
"""
from __future__ import annotations

import re

from paint_rag.models.document import Chunk
from paint_rag.rag.embeddings import EmbeddingModel
from paint_rag.rag.retriever import RetrievedChunk
from paint_rag.rag.vector_store import VectorStore


_TOKEN_RE = re.compile(r"\w+")

_STOPWORDS = frozenset(
    {
        "а", "и", "в", "не", "на", "что", "у", "с", "по", "от", "за",
        "для", "как", "к", "о", "об", "из", "но", "вы", "мы",
        "это", "этот", "эта", "эти", "тот", "всё", "где",
    }
)


def _tokenize(text: str) -> list[str]:
    return [
        t.lower()
        for t in _TOKEN_RE.findall(text)
        if t.lower() not in _STOPWORDS
    ]


def lexical_score(query: str, chunk: Chunk) -> float:
    """Доля query-токенов (без стоп-слов), найденных в chunk."""
    q_tokens = _tokenize(query)
    if not q_tokens:
        return 0.0
    haystack = " ".join(
        filter(None, (chunk.text or "", chunk.product or "", chunk.article or "",
                      chunk.technology or ""))
    ).lower()
    hits = sum(1 for t in q_tokens if t in haystack)
    return hits / len(q_tokens)


def _normalize_cosine(score: float) -> float:
    """Map cosine [-1, 1] to [0, 1]."""
    return (score + 1.0) / 2.0


def hybrid_search(
    vector_store: VectorStore,
    embedding_model: EmbeddingModel,
    query: str,
    *,
    article: str | None = None,
    product: str | None = None,
    technology: str | None = None,
    top_k: int = 5,
    semantic_weight: float = 1.0,
    lexical_weight: float = 1.0,
) -> list[RetrievedChunk]:
    """Hybrid retrieval: semantic + lexical, weighted-sum fusion.

    Возвращает :class:`RetrievedChunk` (тот же тип, что :meth:`Retriever.search`),
    сортированный по убыванию hybrid-score.

    ``semantic_weight=0.0`` — только lexical (semantic не учитывается).
    ``lexical_weight=0.0``  — только semantic (как обычный ``search``).
    """
    # 1. Semantic — существующий search, берём candidates
    query_vec = embedding_model.embed_query(query)
    sem_candidates = vector_store.search(query_vec, top_k=top_k * 4)

    # 2. Lexical scoring
    lex_scores = {
        id(chunk): lexical_score(query, chunk)
        for chunk, _ in sem_candidates
    }

    # 3. Metadata filters (AND)
    def _matches(chunk: Chunk) -> bool:
        if article is not None:
            if (
                chunk.article is None
                or chunk.article.lower().strip() != article.lower().strip()
            ):
                return False
        if product is not None:
            if (
                chunk.product is None
                or chunk.product.lower().strip() != product.lower().strip()
            ):
                return False
        if technology is not None:
            if (
                chunk.technology is None
                or chunk.technology.lower().strip() != technology.lower().strip()
            ):
                return False
        return True

    kept = [
        (chunk, sem_score)
        for chunk, sem_score in sem_candidates
        if _matches(chunk)
    ]
    if not kept:
        return []

    # 4. Fusion
    fused: list[tuple[Chunk, float]] = []
    for chunk, sem_score in kept:
        sem_n = _normalize_cosine(sem_score)
        lex = lex_scores.get(id(chunk), 0.0)
        score = semantic_weight * sem_n + lexical_weight * lex
        fused.append((chunk, score))

    fused.sort(key=lambda pair: pair[1], reverse=True)
    return [
        RetrievedChunk(chunk=c, score=s) for c, s in fused[:top_k]
    ]

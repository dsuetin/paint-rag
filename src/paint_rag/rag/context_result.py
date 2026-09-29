from __future__ import annotations

from pydantic import BaseModel, Field

from paint_rag.rag.retriever import RetrievedChunk


class ContextSource(BaseModel):
    """Нормализованный источник для будущих source citations (Phase 5)."""

    product: str | None = None
    article: str | None = None
    technology: str | None = None
    file: str | None = None
    page: int | None = None
    score: float | None = None
    # Standalone-документ (методическая информация, не Product).
    doc_type: str | None = None
    title: str | None = None
    sheet: str | None = None
    section: str | None = None
    # Coating system provenance
    system_derived: bool = False
    system_names: list[str] = Field(default_factory=list)


class ContextResult(BaseModel):
    """Результат работы ContextBuilder.

    ``chunks`` — релевантные RetrievedChunk (без дублей, в порядке
    убывания score); ``context`` — готовый текст для LLM;
    ``sources`` — нормализованные источники для цитирования;
    ``has_context`` — True, если найден хотя бы один chunk.
    """

    query: str
    chunks: list[RetrievedChunk] = Field(default_factory=list)
    context: str = ""
    sources: list[ContextSource] = Field(default_factory=list)
    has_context: bool = False

"""standalone_to_chunks: StandaloneDocument → list[Chunk].

Цель (Task 9): сохранить текст + провенанс каждого standalone-документа
как отдельный Chunk, который попадает в общий retrieval-индекс вместе
с product-chunks.

Правила:
- **Chunk без source — запрещён** (задачей: «нельзя создавать chunk
  без источника»). Если StandaloneDocument не имеет ``source_file`` —
  бросаем ``ValueError``.
- ``Chunk.product`` / ``Chunk.article`` / ``Chunk.variant_id`` НЕ
  устанавливаем для standalone — это не Product.
- Уникальный ``Chunk.id``: ``standalone:<relpath>:<page|sheet>:<i>``.
- ``chunk.doc_type = "standalone"``, ``chunk.title = title``.
- ``chunk.source = {"file": ..., "page": ..., "sheet": ...,
  "section": ..., "kind": ...}`` — для render'а в CONTEXT и
  citation.
- **Не** создаём structured compatibility relations и не выдумываем
  Product.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Sequence

from paint_rag.models.document import Chunk
from paint_rag.models.standalone import StandaloneDocument


def _hash8(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def _stable_key(source_file: str, page: int | None, sheet: str | None) -> str:
    """Уникальная строка для Chunk.id и de-dup."""
    key = source_file
    if sheet:
        key = f"{key}::{sheet}"
    elif page:
        key = f"{key}::p{page}"
    return key


def _chunk_id(key: str, chunk_id: int) -> str:
    if chunk_id == 0:
        return f"standalone:{key}"
    return f"standalone:{key}#{chunk_id}"


def _make_chunks_for_doc(
    document: StandaloneDocument,
    chunk_size: int,
    overlap: int,
) -> list[Chunk]:
    """Chunk'ит один StandaloneDocument (сохраняя provenance + order)."""
    text = (document.text or "").strip()
    if not text:
        return []
    source_file = (document.source_file or "").strip()
    if not source_file:
        raise ValueError(
            "StandaloneDocument.source_file must not be empty "
            "(chunk без источника — запрещён)"
        )

    # Частичный ключ — для стабильности ID при сохранении/загрузке.
    key = _stable_key(
        source_file,
        document.page,
        document.sheet or document.section,
    )

    # Провенанс в chunk (для ContextBuilder render + citations).
    source: dict[str, object] = {
        "file": Path(source_file).as_posix(),
        "kind": document.kind,
        "doc_type": "standalone",
    }
    if document.page is not None:
        source["page"] = int(document.page)
    if document.sheet:
        source["sheet"] = document.sheet
    if document.section:
        source["section"] = document.section
    if document.title:
        source["title"] = document.title

    chunks: list[Chunk] = []
    text = text.rstrip()
    if not text:
        return []

    start = 0
    idx = 0
    if overlap >= chunk_size or chunk_size <= 0 or overlap < 0:
        raise ValueError(
            f"chunk_size={chunk_size}, overlap={overlap} — invalid"
        )
    step = chunk_size - overlap
    while start < len(text):
        end = min(start + chunk_size, len(text))
        piece = text[start:end].strip()
        if piece:
            chunks.append(
                Chunk(
                    id=_chunk_id(key, idx),
                    text=piece,
                    product=None,
                    article=None,
                    variant_id=0,
                    chunk_id=idx,
                    title=document.title,
                    source=source,
                    doc_type="standalone",
                    related_products=list(document.related_products or []),
                    related_articles=list(document.related_articles or []),
                )
            )
            idx += 1
        start += step
        if end == len(text):
            break
    return chunks


def standalone_to_chunks(
    documents: Sequence[StandaloneDocument],
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[Chunk]:
    """Частичный pipeline: StandaloneDocument(s) → list[Chunk]."""
    out: list[Chunk] = []
    for doc in documents:
        out.extend(_make_chunks_for_doc(doc, chunk_size, overlap))
    return out

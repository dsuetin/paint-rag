from __future__ import annotations

import re
from typing import Optional

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.rag.context_result import ContextResult, ContextSource
from paint_rag.rag.retriever import Retriever, RetrievedChunk


_TD_KEYS = (
    ("gloss", "Степень блеска"),
    ("dry_residue", "Сухой остаток"),
    ("density", "Плотность"),
    ("viscosity", "Вязкость"),
    ("pot_life", "Время жизни смеси"),
    ("drying", "Время сушки"),
    ("shelf_life", "Срок годности"),
    ("application", "Нанесение"),
    ("usage", "Назначение"),
    ("description", "Описание"),
)

# Обобщаемая эвристика: артикул — буквы + цифры (+ дефис/точка).
_ARTICLE_TOKEN_RE = re.compile(
    r"\b[A-Za-z]{1,6}\d{2,6}[A-Za-z0-9]*(?:[-.][A-Za-z0-9]+)*\b"
)


def _norm_code(value: str) -> str:
    return re.sub(r"[\s\-_.]+", "", value).lower()


def _is_code(token: str) -> bool:
    if not token:
        return False
    if len(token) < 3:
        return False
    if not any(ch.isdigit() for ch in token):
        return False
    return any(ch.isalpha() for ch in token)


def _product_codes(product) -> list[str]:
    codes = []
    if product.article:
        codes.append(product.article)
    for alias in product.aliases:
        codes.append(alias)
    for variant in product.variants:
        if variant.article:
            codes.append(variant.article)
    return codes


def detect_article(
    query: str,
    product_store: ProductStore | None = None,
) -> Optional[str]:
    """Найти статью из вопроса, сверяя её с известными products.

    Никаких хардкодовых условий под конкретные артикулы: строим набор
    code-токенов (article + aliases + variant-articles) каждого Product,
    ищем, какой из них встречается в вопросе, и возвращаем каноническую
    ``product.article`` для передачи в ``Retriever``.

    Без ``ProductStore`` используется обобщаемая эвристика — самое
    длинное code-похожее слово с цифрами в вопросе.
    """
    if not query:
        return None

    q = _norm_code(query)

    if product_store is not None:
        best_key: Optional[str] = None
        best_len = -1

        for product in product_store.all():
            for code in _product_codes(product):
                c = _norm_code(code)
                if not _is_code(c) or c not in q:
                    continue
                key = product.article or code
                if len(c) > best_len:
                    best_len = len(c)
                    best_key = key

        if best_key is not None:
            return best_key

        # Есть store, но известного артикула в вопросе нет —
        # не гадаем, чтобы случайно не отфильтровать валидный результат.
        return None

    tokens = _ARTICLE_TOKEN_RE.findall(query)
    numeric = [t for t in tokens if _is_code(t)]
    if numeric:
        return max(numeric, key=len)

    return None


def _source_dict(chunk) -> Optional[dict]:
    return chunk.source


def _to_context_source(rc: RetrievedChunk) -> ContextSource:
    src = _source_dict(rc.chunk) or {}
    if not isinstance(src, dict):
        src = {}
    page = src.get("page")
    return ContextSource(
        product=rc.chunk.product,
        article=rc.chunk.article,
        technology=rc.chunk.technology,
        file=src.get("file"),
        page=int(page) if page is not None else None,
        score=rc.score,
    )


def _format_source_line(index: int) -> str:
    return f"SOURCE {index}"


def _render_chunk_block(index: int, rc: RetrievedChunk) -> str:
    lines = [_format_source_line(index)]

    lines.append(f"Product: {rc.chunk.product}")

    if rc.chunk.article:
        lines.append(f"Article: {rc.chunk.article}")

    if rc.chunk.technology:
        lines.append(f"Technology: {rc.chunk.technology}")

    lines.append(f"Retrieval score: {rc.score:g}")

    src = _source_dict(rc.chunk)
    if isinstance(src, dict):
        file = src.get("file")
        if file:
            source_bits = [file]
            page = src.get("page")
            if page is not None:
                source_bits.append(f"page {page}")
            lines.append("Source: " + ", ".join(source_bits))
        elif src.get("sheet") is not None:
            lines.append(f"Source: {src.get('sheet')}")

    td = rc.chunk.technical_data
    if isinstance(td, dict):
        td_lines = [
            f"{label}: {td[key]}"
            for key, label in _TD_KEYS
            if td.get(key)
        ]
        if td_lines:
            lines.append("")
            lines.append("Technical data:")
            lines.extend(td_lines)

    # Основной текст документа (chunk.text уже содержит
    # название, расход, смешивание и technical data).
    lines.append("")
    lines.append("Document:")
    lines.append(rc.chunk.text.strip())

    return "\n".join(lines)


class ContextBuilder:
    """Собирает контекст для LLM на основе существующего Retriever.

    Не дублирует фильтрацию Retriever: article/product/technology
    передаются прямо в ``Retriever.search``.
    """

    def __init__(
        self,
        retriever: Retriever,
        product_store: ProductStore | None = None,
    ) -> None:
        self.retriever = retriever
        self.product_store = product_store

    def build(
        self,
        query: str,
        top_k: int = 5,
        article: str | None = None,
        product: str | None = None,
        technology: str | None = None,
        max_chunks: int | None = None,
        max_chars: int | None = None,
        *,
        auto_detect_article: bool = True,
    ) -> ContextResult:
        # Автосохранение article из вопроса (только если явно не задан).
        if article is None and auto_detect_article:
            article = detect_article(query, self.product_store)

        results: list[RetrievedChunk] = self.retriever.search(
            query=query,
            top_k=top_k,
            article=article,
            product=product,
            technology=technology,
        )

        results = _dedupe_by_id(results)

        blocks = [
            _render_chunk_block(index, rc)
            for index, rc in enumerate(results, start=1)
        ]
        full_context = "\n\n".join(blocks)

        context, used_chunks = _fit_context(
            results,
            blocks,
            max_chunks=max_chunks,
            max_chars=max_chars,
        )

        sources = [
            _to_context_source(rc)
            for rc in used_chunks
        ]

        return ContextResult(
            query=query,
            chunks=used_chunks,
            context=context,
            sources=sources,
            has_context=bool(used_chunks),
        )


def _dedupe_by_id(
    results: list[RetrievedChunk],
) -> list[RetrievedChunk]:
    seen: set[str] = set()
    ordered: list[RetrievedChunk] = []

    for rc in results:
        key = rc.chunk.id
        if key in seen:
            continue
        seen.add(key)
        ordered.append(rc)

    return ordered


def _fit_context(
    results: list[RetrievedChunk],
    blocks: list[str],
    *,
    max_chunks: int | None,
    max_chars: int | None,
) -> tuple[str, list[RetrievedChunk]]:
    if not results:
        return "", []

    selected_chunks: list[RetrievedChunk] = []
    selected_blocks: list[str] = []
    length = 0

    for rc, block in zip(results, blocks):
        if max_chunks is not None and len(selected_chunks) >= max_chunks:
            break

        added = len(block) + (2 if selected_blocks else 0)

        if max_chars is not None:
            if not selected_blocks and len(block) > max_chars:
                # Первый блок больше лимита: берём только его
                # (обрезая), чтобы контекст не остался пустым.
                # Source-строка (в начале блока) при этом остаётся.
                selected_chunks.append(rc)
                selected_blocks.append(block[:max_chars].rstrip())
                break
            if selected_blocks and length + added > max_chars:
                break

        selected_chunks.append(rc)
        selected_blocks.append(block)
        length += added

    return "\n\n".join(selected_blocks), selected_chunks

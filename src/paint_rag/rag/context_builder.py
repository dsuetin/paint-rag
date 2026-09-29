from __future__ import annotations

import re
from typing import Optional

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.knowledge.systems_store import SystemsStore
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


def _levenshtein(a: str, b: str) -> int:
    """Расстояние Левенштейна (edit distance) — общее, без привязки к
    конкретным артикулам."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    if not a:
        return len(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cur.append(
                min(
                    prev[j] + 1,
                    cur[j - 1] + 1,
                    prev[j - 1] + (ca != cb),
                )
            )
        prev = cur
    return prev[-1]


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


def _detect_substrate_from_query(query: str) -> Optional[str]:
    """Detect substrate from query text.
    
    Uses normalized substrate names from SystemsStore.
    Returns normalized substrate name or None if cannot be determined.
    
    Examples:
        "МДФ" -> "mdf"
        "дверь" -> "door"
        "терраса" -> "terrace"
        "шпон" -> "veneer"
        "массив" -> "wood_solid"
    """
    if not query:
        return None
    
    query_lower = query.lower()
    
    # Substrate mappings - ordered by specificity (materials first, then objects)
    # Material substrates (mdf, veneer, wood_solid) should take priority
    # over object types (door, furniture, table) when both are present
    substrate_mappings = [
        # Material substrates (highest priority)
        ('мдф', 'mdf'),
        ('шпонир', 'veneer'),
        ('шпон', 'veneer'),
        ('массив', 'wood_solid'),
        ('бревн', 'log'),
        # Complex object substrates
        ('столешниц', 'table_table_top'),
        ('лестниц', 'stair'),
        ('террас', 'terrace'),
        ('паркет', 'parquet'),
        ('игрушк', 'child_furniture'),
        ('детска', 'child_furniture'),
        # Simple object substrates
        ('окон', 'window'),
        ('окна', 'window'),
        ('окно', 'window'),
        ('двер', 'door'),
        ('стол', 'table'),
        ('стул', 'chair'),
        ('кухонн', 'kitchen'),
        ('фасад', 'furniture'),  # кухонные фасады
        ('мебель', 'furniture'),
    ]
    
    for keyword, normalized in substrate_mappings:
        if keyword in query_lower:
            return normalized
    
    return None  # Cannot determine substrate


def _detect_application_scope_from_query(query: str) -> Optional[str]:
    """Detect application scope (INTERIOR/EXTERIOR) from query text.
    
    Returns:
        "INTERIOR" - if query clearly indicates interior use
        "EXTERIOR" - if query clearly indicates exterior use
        None - if scope cannot be determined from query
    """
    if not query:
        return None
    
    query_lower = query.lower()
    
    # Strong exterior indicators (take priority)
    strong_exterior = [
        'уличн', 'наружн', 'фасад', 'террас', 'внешн',
        'exterior', 'outdoor'
    ]
    
    # Strong interior indicators
    strong_interior = [
        'внутри', 'интерьер', 'в помещении', 'в комнате',
        'детска', 'внутренн'
    ]
    
    # Weaker indicators (only used if no strong indicators)
    weak_interior = [
        'мебель', 'паркет', 'игрушк'
    ]
    
    has_strong_exterior = any(kw in query_lower for kw in strong_exterior)
    has_strong_interior = any(kw in query_lower for kw in strong_interior)
    has_weak_interior = any(kw in query_lower for kw in weak_interior)
    
    # Strong exterior takes priority
    if has_strong_exterior:
        return "EXTERIOR"
    
    # Strong interior
    if has_strong_interior:
        return "INTERIOR"
    
    # Weak interior only if no exterior
    if has_weak_interior and not has_strong_exterior:
        return "INTERIOR"
    
    return None  # Ambiguous or not specified


def _filter_chunks_by_scope(
    chunks: list[RetrievedChunk],
    required_scope: Optional[str]
) -> list[RetrievedChunk]:
    """Filter chunks by application scope.
    
    Args:
        chunks: Retrieved chunks
        required_scope: "INTERIOR" or "EXTERIOR" from query
        
    Returns:
        Filtered chunks that match the scope requirements:
        - If required_scope is INTERIOR: keep INTERIOR and BOTH
        - If required_scope is EXTERIOR: keep EXTERIOR and BOTH
        - If required_scope is None: keep all chunks
        - UNKNOWN scope chunks are always kept (no documentation = can't filter)
    """
    if not required_scope:
        return chunks  # No filtering needed
    
    filtered = []
    for rc in chunks:
        chunk_scope = rc.chunk.application_scope
        
        # UNKNOWN or None scope - keep (can't filter without documentation)
        if chunk_scope is None or chunk_scope == "UNKNOWN":
            filtered.append(rc)
            continue
        
        # BOTH scope - always compatible
        if chunk_scope == "BOTH":
            filtered.append(rc)
            continue
        
        # Exact match
        if chunk_scope == required_scope:
            filtered.append(rc)
            continue
        
        # EXTERIOR product for INTERIOR query - exclude
        # INTERIOR product for EXTERIOR query - exclude
    
    return filtered


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

        # Точного совпадения нет — пробуем fuzzy-матчинг (опечатка,
        # например PV21O — буква O вместо цифры 0). Обобщаемый алгоритм
        # на расстоянии Левенштейна, без привязки к конкретным артикулам.
        fuzzy_key = _fuzzy_match_article(query, product_store)
        if fuzzy_key is not None:
            return fuzzy_key

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
        doc_type=rc.chunk.doc_type or src.get("doc_type"),
        title=rc.chunk.title or src.get("title"),
        sheet=src.get("sheet"),
        section=src.get("section"),
        system_derived=src.get("system_derived", False),
        system_names=src.get("system_names", []),
    )


def _format_source_line(index: int) -> str:
    return f"SOURCE {index}"


def _render_chunk_block(index: int, rc: RetrievedChunk) -> str:
    lines = [_format_source_line(index)]

    is_standalone = rc.chunk.doc_type == "standalone"

    if is_standalone:
        # Standalone-документ — это не Product: показываем Title и
        # полный provenance (file + page/sheet), без Product/Article.
        if rc.chunk.title:
            lines.append(f"Title: {rc.chunk.title}")
    else:
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
            sheet = src.get("sheet")
            if sheet is not None:
                source_bits.append(f"sheet {sheet}")
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


def _fuzzy_match_article(
    query: str,
    product_store: ProductStore,
    min_similarity: float = 0.6,
) -> Optional[str]:
    """Fuzzy-поиск статьи по code-токенам вопроса (расстояние Левенштейна).

    Обобщаемый алгоритм: покрывает опечатки в известном артикуле
    (например, буква O вместо цифры 0). Без привязки к конкретным
    продуктам. Возвращает каноническую ``product.article`` лучшего
    совпадения при сходстве >= ``min_similarity``; иначе ``None``.
    """
    # Кандидаты: нормализованные code-строки -> канонический article.
    candidates: dict[str, str] = {}
    for product in product_store.all():
        for code in _product_codes(product):
            c = _norm_code(code)
            if not _is_code(c):
                continue
            key = product.article or code
            candidates.setdefault(c, key)

    best: Optional[str] = None
    best_sim = 0.0

    for token in _ARTICLE_TOKEN_RE.findall(query):
        if not _is_code(token):
            continue
        tn = _norm_code(token)
        for cand, canonical in candidates.items():
            dist = _levenshtein(tn, cand)
            max_len = max(len(tn), len(cand))
            if max_len == 0:
                continue
            sim = (max_len - dist) / max_len
            if sim > best_sim:
                best_sim = sim
                best = canonical

    if best is not None and best_sim >= min_similarity:
        return best
    return None


def _query_has_unknown_code_token(
    query: str,
    product_store: ProductStore | None,
    min_similarity: float = 0.6,
) -> bool:
    """True, если в вопросе есть code-подобный токен, НЕ совпадающий ни с
    одним известным продуктом (и не похожий ни на один). Признак вопроса
    о неизвестном продукте → отказ, а не «лучшее соответствие»."""
    if product_store is None:
        return False
    tokens = _ARTICLE_TOKEN_RE.findall(query)
    code_tokens = [t for t in tokens if _is_code(t)]
    if not code_tokens:
        return False
    q_norm = _norm_code(query)
    # Фuzzy-совпадение считаем «известным» (это опечатка, а не отказ).
    if _fuzzy_match_article(query, product_store, min_similarity) is not None:
        return False
    for product in product_store.all():
        for code in _product_codes(product):
            c = _norm_code(code)
            if _is_code(c) and c in q_norm:
                return False
    return True


class ContextBuilder:
    """Собирает контекст для LLM на основе существующего Retriever.

    Не дублирует фильтрацию Retriever: article/product/technology
    передаются прямо в ``Retriever.search``.
    """

    def __init__(
        self,
        retriever: Retriever,
        product_store: ProductStore | None = None,
        systems_store: SystemsStore | None = None,
    ) -> None:
        self.retriever = retriever
        self.product_store = product_store
        self.systems_store = systems_store

    def build(
        self,
        query: str,
        top_k: int = 15,
        article: str | None = None,
        product: str | None = None,
        technology: str | None = None,
        max_chunks: int | None = None,
        max_chars: int | None = None,
        *,
        auto_detect_article: bool = True,
        use_hybrid: bool = True,
        semantic_weight: float = 1.0,
        lexical_weight: float = 1.5,
        use_systems: bool = True,
    ) -> ContextResult:
        # Автосохранение article из вопроса (только если явно не задан).
        if article is None and auto_detect_article:
            article = detect_article(query, self.product_store)

        # Консервативный отказ: вопрос содержит code-токен неизвестного
        # продукта (не совпадает ни с одним product/alias) и явных фильтров
        # нет. Refuse ДО обращения к retriever: retrieved chunks были бы
        # нерелевантными, и LLM не должен отвечать чужими данными.
        if (
            auto_detect_article
            and article is None
            and product is None
            and technology is None
            and self.product_store is not None
            and _query_has_unknown_code_token(query, self.product_store)
        ):
            return ContextResult(
                query=query,
                chunks=[],
                context="",
                sources=[],
                has_context=False,
            )

        # Semantic retrieval
        if use_hybrid:
            semantic_results: list[RetrievedChunk] = self.retriever.search_hybrid(
                query=query,
                top_k=top_k,
                article=article,
                product=product,
                technology=technology,
                semantic_weight=semantic_weight,
                lexical_weight=lexical_weight,
            )
        else:
            semantic_results = self.retriever.search(
                query=query,
                top_k=top_k,
                article=article,
                product=product,
                technology=technology,
            )

        # System-based retrieval (structured candidates)
        system_results: list[RetrievedChunk] = []
        if use_systems and self.systems_store is not None:
            system_results = self._get_system_chunks(query, top_k)

        # Merge: system results get higher priority (prepended)
        all_results = system_results + semantic_results

        # Deduplicate by chunk id (keep first occurrence = system priority)
        results = _dedupe_by_id(all_results)

        # Filter by application scope if query indicates interior/exterior
        required_scope = _detect_application_scope_from_query(query)
        if required_scope:
            results = _filter_chunks_by_scope(results, required_scope)

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

    def _get_system_chunks(
        self,
        query: str,
        top_k: int
    ) -> list[RetrievedChunk]:
        """Get chunks from coating systems matching the query substrate.
        
        Returns system-derived chunks with provenance metadata.
        """
        from paint_rag.knowledge.systems_store import normalize_substrate
        
        # Detect substrate from query
        substrate = _detect_substrate_from_query(query)
        if not substrate:
            return []
        
        # Normalize substrate
        normalized = normalize_substrate(substrate)
        if not normalized:
            return []
        
        # Find matching systems
        matching_systems = self.systems_store.find_by_substrate(normalized)
        if not matching_systems:
            return []
        
        # Collect chunk IDs from system products
        system_chunk_ids = set()
        for system in matching_systems:
            for layer in (system.layers or []):
                if layer.article:
                    system_chunk_ids.add(layer.article)
                # Also match by product name if article not available
                if layer.name and self.product_store:
                    for product in self.product_store.all():
                        if layer.name.lower() in product.name.lower():
                            if product.article:
                                system_chunk_ids.add(product.article)
        
        if not system_chunk_ids:
            return []
        
        # Retrieve chunks for system products
        system_chunks = []
        for article in system_chunk_ids:
            chunks = self.retriever.search(
                query=query,
                top_k=top_k // max(len(system_chunk_ids), 1),
                article=article,
            )
            for rc in chunks:
                # Add system provenance to source
                if not rc.chunk.source:
                    rc.chunk.source = {}
                rc.chunk.source['system_derived'] = True
                rc.chunk.source['system_names'] = [
                    s.name for s in matching_systems 
                    if any(l.article == article or 
                           (l.name and article in (l.name or '')) 
                           for l in (s.layers or []))
                ]
            system_chunks.extend(chunks)
        
        return system_chunks


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

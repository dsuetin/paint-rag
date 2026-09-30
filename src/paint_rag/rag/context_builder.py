from __future__ import annotations

import re
from typing import Optional

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.knowledge.systems_store import SystemsStore
from paint_rag.rag.context_result import (
    ContextResult,
    ContextSource,
    RecommendationMetadata,
)
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
        # Outdoor furniture (before generic furniture to be more specific)
        ('уличн мебель', 'outdoor_furniture'),
        ('мебель уличн', 'outdoor_furniture'),
        ('мебель для улицы', 'outdoor_furniture'),
        ('outdoor furniture', 'outdoor_furniture'),
        ('furniture outdoor', 'outdoor_furniture'),
        ('уличн', 'outdoor'),  # уличная -> outdoor
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
    
    # Strong exterior indicators
    strong_exterior = [
        'уличн', 'наружн', 'террас', 'внешн', 'снаружн',
        'exterior', 'outdoor'
    ]
    
    # Interior indicators
    interior_indicators = [
        'кухонн', 'кухня', 'паркет', 'детска', 'игрушк',
        'внутри', 'интерьер', 'в помещении', 'в комнате',
        'внутренн', 'шкаф', 'мебель для кухонн', 'мебель для кухн'
    ]
    
    # "фасад" is ambiguous:
    # - "фасад здания" / "фасад дома" = EXTERIOR
    # - "кухонные фасады" / "мебельные фасады" = INTERIOR
    facade_interior_context = [
        'кухонн фасад', 'фасад кухонн', 'мебельн фасад',
        'фасад мебель', 'фасад шкаф', 'мебель для кухонн',
        'мебельн', 'фасад'  # generic: мебельные фасады
    ]
    facade_exterior_context = [
        'фасад здани', 'фасад дом', 'фасад наружн',
        'фасад уличн'
    ]
    
    # Exterior furniture context (explicit outdoor furniture)
    exterior_furniture_context = [
        'уличн мебель', 'мебель уличн', 'наружн мебель',
        'мебель наружн', 'outdoor furniture', 'furniture outdoor'
    ]
    
    # Interior furniture context
    interior_furniture_context = [
        'мебель для кухонн', 'кухонн мебель', 'мебель кухонн'
    ]
    
    has_strong_exterior = any(kw in query_lower for kw in strong_exterior)
    has_interior = any(kw in query_lower for kw in interior_indicators)
    has_facade_interior = any(kw in query_lower for kw in facade_interior_context)
    has_facade_exterior = any(kw in query_lower for kw in facade_exterior_context)
    has_exterior_furniture = any(kw in query_lower for kw in exterior_furniture_context)
    has_interior_furniture = any(kw in query_lower for kw in interior_furniture_context)
    
    # Exterior facade context
    if has_facade_exterior:
        return "EXTERIOR"
    
    # Exterior furniture context (explicit outdoor furniture)
    if has_exterior_furniture:
        return "EXTERIOR"
    
    # Strong exterior indicators
    if has_strong_exterior:
        return "EXTERIOR"
    
    # Interior furniture context
    if has_facade_interior or has_interior_furniture:
        return "INTERIOR"
    
    # Strong interior indicators
    if has_interior:
        return "INTERIOR"
    
    return None  # Ambiguous or not specified


def _get_chunk_scope(rc: RetrievedChunk) -> Optional[str]:
    """Get application scope from chunk.
    
    Priority:
    1. chunk.application_scope (if set)
    2. system_scopes from chunk.source (use most restrictive)
    3. None (unknown)
    """
    chunk_scope = rc.chunk.application_scope
    
    # If chunk has system_scopes in source, use the most restrictive one
    if not chunk_scope and rc.chunk.source:
        system_scopes = rc.chunk.source.get('system_scopes', [])
        if system_scopes:
            # Use the most restrictive scope
            # INTERIOR-only is more restrictive than BOTH
            if "INTERIOR" in system_scopes and "BOTH" not in system_scopes:
                chunk_scope = "INTERIOR"
            elif "EXTERIOR" in system_scopes and "BOTH" not in system_scopes:
                chunk_scope = "EXTERIOR"
            elif "BOTH" in system_scopes:
                chunk_scope = "BOTH"
            elif system_scopes:
                chunk_scope = system_scopes[0]
    
    return chunk_scope


def _get_scope_priority(chunk_scope: Optional[str], required_scope: str) -> float:
    """Get ranking priority for a chunk based on its scope vs required scope.
    
    Higher priority = better match.
    
    For INTERIOR queries:
        INTERIOR = 4.0 (best match - specialized for interior)
        BOTH = 2.0 (valid alternative - universal)
        EXTERIOR = 1.0 (lower priority - specialized for exterior)
        UNKNOWN = 0.5 (no info)
    
    For EXTERIOR queries:
        EXTERIOR = 4.0 (best match - specialized for exterior)
        BOTH = 2.0 (valid alternative - universal)
        INTERIOR = 1.0 (lower priority - specialized for interior)
        UNKNOWN = 0.5 (no info)
    """
    if chunk_scope is None or chunk_scope == "UNKNOWN":
        return 0.5  # Unknown scope gets lowest priority
    
    if required_scope == "INTERIOR":
        if chunk_scope == "INTERIOR":
            return 4.0  # Perfect match - specialized for interior
        elif chunk_scope == "BOTH":
            return 2.0  # Valid alternative - universal
        elif chunk_scope == "EXTERIOR":
            return 1.0  # Lower priority but still valid
    
    elif required_scope == "EXTERIOR":
        if chunk_scope == "EXTERIOR":
            return 4.0  # Perfect match - specialized for exterior
        elif chunk_scope == "BOTH":
            return 2.0  # Valid alternative - universal
        elif chunk_scope == "INTERIOR":
            return 1.0  # Lower priority but still valid
    
    return 0.5  # Default


def _rank_chunks_by_scope(
    chunks: list[RetrievedChunk],
    required_scope: Optional[str]
) -> list[RetrievedChunk]:
    """Rank chunks by application scope priority (in-place modification of scores).
    
    This is NOT a filter - all chunks are kept, but their scores are adjusted
    based on how well their application scope matches the query requirements.
    
    Args:
        chunks: Retrieved chunks (will be modified in-place)
        required_scope: "INTERIOR" or "EXTERIOR" from query
        
    Returns:
        Same chunks list with adjusted scores for ranking
    """
    if not required_scope:
        return chunks  # No ranking needed
    
    # Adjust scores based on scope priority
    for rc in chunks:
        chunk_scope = _get_chunk_scope(rc)
        priority = _get_scope_priority(chunk_scope, required_scope)
        
        # Multiply original score by priority factor
        # This preserves relative ordering within same scope while boosting better matches
        rc.score = rc.score * priority
    
    # Sort by adjusted score (descending)
    chunks.sort(key=lambda rc: rc.score, reverse=True)
    
    return chunks


def _boost_interior_over_both(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Additional boost for INTERIOR-only systems over BOTH systems.
    
    This ensures that specialized INTERIOR systems are ranked higher than
    universal BOTH systems, even when they have similar base scores.
    
    For INTERIOR queries:
    - INTERIOR-only systems get +1.0 bonus
    - BOTH systems get no bonus
    
    This creates a clear separation between specialized and universal systems.
    """
    for rc in chunks:
        chunk_scope = _get_chunk_scope(rc)
        
        # Boost INTERIOR-only systems
        if chunk_scope == "INTERIOR":
            rc.score += 1.0
    
    # Re-sort after bonus
    chunks.sort(key=lambda rc: rc.score, reverse=True)
    
    return chunks


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
        system_scopes=src.get("system_scopes", []),
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

    # Add priority indicator based on score
    # Higher score = higher priority
    score = rc.score
    if score >= 20:
        priority = "HIGH PRIORITY"
    elif score >= 10:
        priority = "MEDIUM PRIORITY"
    else:
        priority = "LOWER PRIORITY"
    
    lines.append(f"Priority: {priority} (score: {score:g})")

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

        # Sort by score (descending) to prioritize higher-scoring chunks
        results.sort(key=lambda rc: rc.score, reverse=True)

        # Rank by application scope if query indicates interior/exterior
        # This adjusts scores based on scope match (NOT a filter)
        required_scope = _detect_application_scope_from_query(query)
        if required_scope:
            results = _rank_chunks_by_scope(results, required_scope)
        
        # Additional boost for specialized interior systems over universal BOTH systems
        # This ensures INTERIOR-only systems are ranked higher than BOTH systems
        # even when they have similar base scores
        if required_scope == "INTERIOR":
            results = _boost_interior_over_both(results)

        # Build recommendation metadata from ranked results
        # This is the DETERMINISTIC selection - code chooses primary, not LLM
        primary_recommendation = None
        alternatives = []
        
        if results:
            # Group chunks by system to get unique systems
            system_chunks: dict[str, list[RetrievedChunk]] = {}
            for rc in results:
                source = rc.chunk.source or {}
                system_names = source.get('system_names', [])
                for system_name in system_names:
                    if system_name not in system_chunks:
                        system_chunks[system_name] = []
                    system_chunks[system_name].append(rc)
            
            # Build recommendation metadata for each system
            rank = 1
            for system_name, chunks in system_chunks.items():
                # Get best score for this system
                best_score = max(rc.score for rc in chunks)
                
                # Get application scope from first chunk
                first_chunk = chunks[0].chunk
                system_scopes = first_chunk.source.get('system_scopes', []) if first_chunk.source else []
                app_scope = system_scopes[0] if system_scopes else None
                
                # Determine ranking factors
                ranking_factors = []
                if app_scope == "INTERIOR":
                    ranking_factors.append("INTERIOR scope (specialized for interior)")
                elif app_scope == "EXTERIOR":
                    ranking_factors.append("EXTERIOR scope (specialized for exterior)")
                elif app_scope == "BOTH":
                    ranking_factors.append("BOTH scope (universal)")
                
                if best_score >= 20:
                    ranking_factors.append(f"High relevance score ({best_score:g})")
                
                metadata = RecommendationMetadata(
                    rank=rank,
                    system_name=system_name,
                    score=best_score,
                    application_scope=app_scope,
                    is_primary=(rank == 1),
                    ranking_factors=ranking_factors,
                )
                
                if rank == 1:
                    primary_recommendation = metadata
                else:
                    alternatives.append(metadata)
                
                rank += 1
        
        # Add PRIMARY RECOMMENDATION header before chunks
        primary_header = []
        if primary_recommendation:
            primary_header.append("PRIMARY RECOMMENDATION (DETERMINISTIC SELECTION):")
            primary_header.append(f"  System: {primary_recommendation.system_name}")
            primary_header.append(f"  Application Scope: {primary_recommendation.application_scope or 'UNKNOWN'}")
            primary_header.append(f"  Score: {primary_recommendation.score:g}")
            if primary_recommendation.ranking_factors:
                primary_header.append("  Ranking Factors:")
                for factor in primary_recommendation.ranking_factors:
                    primary_header.append(f"    - {factor}")
            primary_header.append("")
            primary_header.append("  INSTRUCTION: You MUST recommend this system as the primary choice.")
            primary_header.append("  Do not select a different system based on your own reasoning.")
            primary_header.append("")
        
        blocks = [
            _render_chunk_block(index, rc)
            for index, rc in enumerate(results, start=1)
        ]
        
        # Join with primary header
        if primary_header:
            full_context = "\n".join(primary_header) + "\n" + "\n\n".join(blocks)
        else:
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
            primary_recommendation=primary_recommendation,
            alternatives=alternatives,
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
        
        # Filter and prioritize systems by application scope if query indicates interior/exterior
        required_scope = _detect_application_scope_from_query(query)
        if required_scope:
            filtered_systems = []
            for system in matching_systems:
                # Use application_scope from model if available, otherwise derive from item_types
                system_scope = system.application_scope
                if not system_scope:
                    # Fallback: derive from item_types for legacy systems
                    item_types = (system.item_types or '').lower()
                    is_exterior = any(kw in item_types for kw in [
                        'снаруж', 'уличн', 'наружн', 'exterior', 'outdoor'
                    ])
                    is_interior = any(kw in item_types for kw in [
                        'внутренн', 'интерьер', 'кухн', 'мебель'
                    ])
                    if is_exterior and is_interior:
                        system_scope = "BOTH"
                    elif is_exterior:
                        system_scope = "EXTERIOR"
                    elif is_interior:
                        system_scope = "INTERIOR"
                    else:
                        system_scope = "UNKNOWN"
                
                # Filter based on required scope
                if required_scope == 'INTERIOR' and system_scope == 'EXTERIOR':
                    # Skip exterior-only systems for interior queries
                    continue
                elif required_scope == 'EXTERIOR' and system_scope == 'INTERIOR':
                    # Skip interior-only systems for exterior queries
                    continue
                
                # Add with priority score (for ranking)
                # INTERIOR-only systems get higher priority for INTERIOR queries
                priority = 1.0
                if required_scope == 'INTERIOR' and system_scope == 'INTERIOR':
                    priority = 2.0  # Boost interior-only systems
                elif required_scope == 'EXTERIOR' and system_scope == 'EXTERIOR':
                    priority = 2.0  # Boost exterior-only systems
                
                filtered_systems.append((system, priority))
            
            # Sort by priority (higher first)
            filtered_systems.sort(key=lambda x: x[1], reverse=True)
            matching_systems = [s[0] for s in filtered_systems]
            
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
                
                # Find which systems this chunk belongs to
                chunk_article = rc.chunk.article or ''
                chunk_product = rc.chunk.product or ''
                
                matching_system_names = []
                matching_system_scopes = []
                for s in matching_systems:
                    for l in (s.layers or []):
                        # Match by article
                        if l.article and l.article == chunk_article:
                            matching_system_names.append(s.name)
                            if s.application_scope:
                                matching_system_scopes.append(s.application_scope)
                            break
                        # Match by layer name in product name
                        if l.name and l.name.lower() in chunk_product.lower():
                            matching_system_names.append(s.name)
                            if s.application_scope:
                                matching_system_scopes.append(s.application_scope)
                            break
                
                rc.chunk.source['system_names'] = list(set(matching_system_names))
                if matching_system_scopes:
                    rc.chunk.source['system_scopes'] = list(set(matching_system_scopes))
            
            system_chunks.extend(chunks)
        
        # Add system info chunks for systems without product articles
        # This ensures systems like "Кислотная" with generic layer names (ПУ-, Трэфф Тэксурф) are included
        for system in matching_systems:
            # Check if this system already has chunks
            has_chunks = any(
                system.name in (rc.chunk.source.get('system_names') or [])
                for rc in system_chunks
            )
            
            if not has_chunks and system.item_types:
                # Create a synthetic chunk with system information
                from paint_rag.models.document import Chunk
                
                system_text = f"Система: {system.name}\n"
                if system.item_types:
                    system_text += f"Назначение: {system.item_types}\n"
                if system.application_scope:
                    system_text += f"Область применения: {system.application_scope}\n"
                if system.layers:
                    system_text += "Состав системы:\n"
                    for layer in system.layers:
                        system_text += f"  - {layer.role}: {layer.name}\n"
                if system.substrates:
                    system_text += f"Подложки: {', '.join(system.substrates)}\n"
                if system.advantages:
                    system_text += f"Преимущества: {system.advantages}\n"
                if system.disadvantages:
                    system_text += f"Недостатки: {system.disadvantages}\n"
                
                from paint_rag.rag.context_result import ContextSource
                import uuid
                
                system_source = ContextSource(
                    system_derived=True,
                    system_names=[system.name],
                    system_scopes=[system.application_scope] if system.application_scope else [],
                    provenance=system.source.model_dump() if system.source else None,
                )
                
                system_chunk = Chunk(
                    id=f"system_{uuid.uuid4()}",
                    text=system_text,
                    chunk_id=0,
                    source=system_source.model_dump(),
                )
                
                # Add with high priority for matching scope
                from paint_rag.rag.context_result import RetrievedChunk
                
                # Calculate priority based on scope match
                priority = 1.0
                if required_scope and system.application_scope:
                    if required_scope == system.application_scope:
                        priority = 3.0  # Exact match gets highest priority
                    elif system.application_scope == "BOTH":
                        priority = 2.0  # BOTH systems get medium priority
                
                system_chunks.append(RetrievedChunk(
                    chunk=system_chunk,
                    score=priority * 2.0,  # Base score for system info, boosted by priority
                ))
        
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

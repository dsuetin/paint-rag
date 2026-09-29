from typing import Optional

from paint_rag.models.document import Document, Chunk
from paint_rag.models.product import Product, ApplicationLayer
from paint_rag.models.product_relation import (
    ProductRelation,
    RelationAlternative,
    RelationSource,
)


def _render_relation_source(
    source: RelationSource,
) -> Optional[str]:
    bits: list[str] = []
    if source.file:
        bits.append(source.file)
    if source.page is not None:
        bits.append(f"стр. {source.page}")
    if source.sheet:
        bits.append(source.sheet)
    if source.row is not None:
        bits.append(f"строка {source.row}")
    if bits:
        return "; ".join(bits)
    return None


def _render_compatibility_block(
    relations: list[ProductRelation],
) -> list[str]:
    if not relations:
        return [
            "Совместимость: "
            "документированных подтверждённых связей не найдено "
            "(UNKNOWN; отсутствие связи не означает запрет)"
        ]
    lines = [
        "Совместимость "
        "(только задокументированные связи, каждая с источником):"
    ]
    for rel in relations:
        label = (
            "CONFIRMED (совместимо)"
            if rel.status == "CONFIRMED"
            else "FORBIDDEN (несовместимо/запрещено)"
        )
        line = f"- [{label}] base: {rel.base} -> top: {rel.top}"
        if rel.base_product or rel.top_product:
            names = " / ".join(
                n for n in (rel.base_product, rel.top_product) if n
            )
            if names:
                line += f" ({names})"
        if rel.reason:
            line += f" Причина: {rel.reason}"
        if rel.conditions:
            line += f" Условия: {'; '.join(rel.conditions)}"
        src = _render_relation_source(rel.source)
        if src:
            line += f" Источник: {src}"
        if rel.alternatives:
            alt_bits = [
                f"{a.ref}" + (f" ({a.role})" if a.role else "")
                for a in rel.alternatives
            ]
            line += f" Альтернативы: {', '.join(alt_bits)}"
        lines.append(line)
    return lines


def _render_alternatives_block(
    alternatives: list[RelationAlternative],
) -> list[str]:
    if not alternatives:
        return []
    lines = [
        "Альтернативы компонентов "
        "(«или» в рецептуре, это не coating-compatibility):"
    ]
    for alt in alternatives:
        line = f"- {alt.ref}"
        if alt.role:
            line += f" (роль: {alt.role})"
        if alt.note:
            line += f" Комментарий: {alt.note}"
        lines.append(line)
    return lines


def _product_relation_payload(
    relations: list[ProductRelation],
) -> list[dict]:
    return [rel.model_dump() for rel in relations]


def _alternative_payload(
    alternatives: list[RelationAlternative],
) -> list[dict]:
    return [alt.model_dump() for alt in alternatives]


def _render_application_order(
    order: list[ApplicationLayer],
) -> list[str]:
    """Рендерит последовательность нанесения в текст."""
    if not order:
        return []
    
    lines = ["Порядок нанесения:"]
    
    for i, layer in enumerate(order, 1):
        line = f"{i}. {layer.role}"
        
        if layer.product_name:
            line += f" — {layer.product_name}"
        
        if layer.article:
            line += f" ({layer.article})"
        
        if layer.layers_count:
            line += f", количество: {layer.layers_count}"
        
        if layer.notes:
            line += f" ({layer.notes})"
        
        lines.append(line)
    
    return lines


def documents_to_chunks(
    documents: list[Document],
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[Chunk]:

    chunks: list[Chunk] = []

    for document in documents:
        chunks.extend(
            document_to_chunks(
                document=document,
                chunk_size=chunk_size,
                overlap=overlap,
            )
        )

    return chunks

def product_to_documents(
    product: Product,
) -> list[Document]:

    documents: list[Document] = []

    # Если у продукта есть варианты — делаем документ
    # на каждый вариант.
    if product.variants:
        variants = product.variants

    # Для продуктов из PDF variants может не быть.
    # Всё равно создаём один документ.
    else:
        variants = [None]

    for index, variant in enumerate(variants):

        variant_id = (
            variant.variant_id
            if variant is not None
            else 1
        )

        parts: list[str] = []

        parts.append(
            f"Название: {product.name}"
        )

        if product.article:
            parts.append(
                f"Артикул: {product.article}"
            )

        if product.technology:
            parts.append(
                f"Технология: {product.technology}"
            )

        if product.aliases:
            parts.append(
                "Алиасы: "
                + ", ".join(product.aliases)
            )

        if product.consumption_min is not None:
            consumption = (
                f"Рекомендованный расход: "
                f"{product.consumption_min}"
            )

            if product.consumption_max is not None:
                consumption += (
                    f"–{product.consumption_max}"
                )

            if product.consumption_unit:
                consumption += (
                    f" {product.consumption_unit}"
                )

            parts.append(consumption)

        if product.max_layers is not None:
            parts.append(
                f"Рекомендованное количество "
                f"слоев: не более "
                f"{product.max_layers}"
            )

        mixing = (
            product.mixing
            if product.mixing is not None
            else (
                variant.mixing
                if variant is not None
                else None
            )
        )

        if mixing:
            mixing_parts = [
                f"{mixing.base_percent:g}%"
            ]

            def _component(
                name: "Optional[str]",
                percent: "Optional[float]",
                percent_min: "Optional[float]",
                percent_max: "Optional[float]",
            ) -> "Optional[str]":
                if percent is not None:
                    value = f"{percent:g}%"
                elif (
                    percent_min is not None
                    and percent_max is not None
                ):
                    if percent_min == percent_max:
                        value = f"{percent_min:g}%"
                    else:
                        value = (
                            f"{percent_min:g}"
                            f"-"
                            f"{percent_max:g}%"
                        )
                else:
                    return None
                return (
                    f"{name} {value}" if name else value
                )

            if mixing.hardener is not None:
                part = _component(
                    mixing.hardener.name,
                    mixing.hardener.percent,
                    mixing.hardener.percent_min,
                    mixing.hardener.percent_max,
                )
                if part:
                    mixing_parts.append(part)

            if mixing.thinner is not None:
                part = _component(
                    mixing.thinner.name,
                    mixing.thinner.percent,
                    mixing.thinner.percent_min,
                    mixing.thinner.percent_max,
                )
                if part:
                    mixing_parts.append(part)

            parts.append(
                "Пропорции смешивания: "
                + " + ".join(mixing_parts)
            )

            if mixing.raw:
                parts.append(
                    f"Исходная запись: {mixing.raw}"
                )

        if product.technical_data is not None:
            td = product.technical_data
            td_parts: list[str] = []
            _TD_LABELS = [
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
            ]
            for key, label in _TD_LABELS:
                val = getattr(td, key, None)
                if val:
                    td_parts.append(f"{label}: {val}")
            if td_parts:
                parts.append(
                    "Технические характеристики:\n" + "\n".join(td_parts)
                )

        relations = product.effective_compatibility(variant)
        parts.extend(_render_compatibility_block(relations))

        alt_lines: list[str] = []
        if variant is not None and variant.alternatives:
            alt_lines.extend(
                _render_alternatives_block(variant.alternatives)
            )
        alt_lines.extend(_render_alternatives_block(product.alternatives))
        if alt_lines:
            parts.extend(alt_lines)

        # Порядок нанесения
        if product.application_order:
            parts.extend(_render_application_order(product.application_order))

        # Химическая система
        if product.chemical_system:
            cs = product.chemical_system
            cs_text = f"Химическая система: {cs.code}"
            if cs.provenance:
                prov = cs.provenance
                if prov.file:
                    cs_text += f" (источник: {prov.file[:50]}...)"
            parts.append(cs_text)

        # Роли продукта
        if product.application_roles:
            roles_text = "Роли: " + ", ".join(product.application_roles)
            parts.append(roles_text)

        # Область применения
        if product.application_scope:
            scope = product.application_scope.value if hasattr(product.application_scope, 'value') else product.application_scope
            scope_text = f"Область применения: {scope}"
            if product.application_scope_source:
                scope_text += f" (источник: {product.application_scope_source[:50]}...)"
            parts.append(scope_text)

        relation_sources: list[RelationSource] = (
            [rel.source for rel in relations if rel.source.has_provenance]
        )
        if variant is not None:
            relation_sources.extend(
                s for s in variant.sources if s.has_provenance
            )
        relation_sources.extend(
            s for s in product.sources if s.has_provenance
        )

        text = "\n".join(parts)

        documents.append(
            Document(
                product=product.name,
                variant_id=variant_id,
                article=product.article,
                text=text,
                metadata={
                    "technology": product.technology,
                    "source": (
                        product.source.model_dump()
                        if product.source
                        else None
                    ),
                    "technical_data": (
                        product.technical_data.model_dump(
                            exclude_none=True
                        )
                        if product.technical_data
                        else None
                    ),
                    "compatibility": (
                        _product_relation_payload(relations)
                        if relations
                        else None
                    ),
                    "alternatives": (
                        _alternative_payload(
                            list(product.alternatives)
                            + (
                                list(variant.alternatives)
                                if variant is not None
                                else []
                            )
                        )
                        if (
                            product.alternatives
                            or (
                                variant is not None
                                and variant.alternatives
                            )
                        )
                        else None
                    ),
                    "relation_sources": (
                        [s.model_dump() for s in relation_sources]
                        if relation_sources
                        else None
                    ),
                     "application_order": (
                         [l.model_dump() for l in product.application_order]
                         if product.application_order
                         else None
                     ),
                     "chemical_system": (
                         product.chemical_system.model_dump()
                         if product.chemical_system
                         else None
                     ),
                     "application_roles": (
                         product.application_roles
                         if product.application_roles
                         else None
                     ),
                     "application_scope": (
                         product.application_scope.value if hasattr(product.application_scope, 'value') else product.application_scope
                         if product.application_scope
                         else None
                     ),
                 },
            )
        )
        documents[-1].chunks = document_to_chunks(
            documents[-1],
            chunk_size=500,
            overlap=50,
        )

    return documents


def document_to_chunks(
    document: Document,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[Chunk]:

    if chunk_size <= 0:
        raise ValueError(
            "chunk_size must be > 0"
        )

    if overlap < 0:
        raise ValueError(
            "overlap must be >= 0"
        )

    if overlap >= chunk_size:
        raise ValueError(
            "overlap must be < chunk_size"
        )

    text = document.text.strip()

    if not text:
        return []

    chunks: list[Chunk] = []

    start = 0
    chunk_id = 0

    step = chunk_size - overlap

    while start < len(text):

        end = min(
            start + chunk_size,
            len(text),
        )

        chunk_text = text[start:end].strip()

        if chunk_text:
            chunks.append(
                Chunk(
                    id=f"{document.article}:{document.variant_id}:{chunk_id}",
                    text=chunk_text,
                    article=document.article,
                    product=document.product,
                    variant_id=document.variant_id,
                    chunk_id=chunk_id,
                    technology=document.metadata.get("technology"),
                    technical_data=document.metadata.get("technical_data"),
                    source=document.metadata.get("source"),
                    compatibility=document.metadata.get("compatibility"),
                    alternatives=document.metadata.get("alternatives"),
                    relation_sources=document.metadata.get(
                        "relation_sources"
                    ),
                     application_order=document.metadata.get(
                         "application_order"
                     ),
                     chemical_system=document.metadata.get(
                         "chemical_system"
                     ),
                     application_roles=document.metadata.get(
                         "application_roles"
                     ),
                     application_scope=document.metadata.get(
                         "application_scope"
                     ),
                 )
             )

            chunk_id += 1

        start += step

    return chunks
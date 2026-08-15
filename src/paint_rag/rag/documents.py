from paint_rag.models.document import Document, Chunk
from paint_rag.models.product import Product


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

            if mixing.hardener:
                hardener = mixing.hardener

                if hardener.name:
                    mixing_parts.append(
                        f"{hardener.name} "
                        f"{hardener.percent:g}%"
                    )
                else:
                    mixing_parts.append(
                        f"{hardener.percent:g}%"
                    )

            if mixing.thinner:
                thinner = mixing.thinner

                if thinner.name:
                    mixing_parts.append(
                        f"{thinner.name} "
                        f"{thinner.percent:g}%"
                    )
                else:
                    mixing_parts.append(
                        f"{thinner.percent:g}%"
                    )

            parts.append(
                "Пропорции смешивания: "
                + " + ".join(mixing_parts)
            )

            if mixing.raw:
                parts.append(
                    f"Исходная запись: {mixing.raw}"
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
                    id=f"{document.article}:{document.variant_id}:0",
                    text=chunk_text,
                    article=document.article,
                    product=document.product,
                    variant_id=document.variant_id,
                    chunk_id=chunk_id,
                )
            )

            chunk_id += 1

        start += step

    return chunks
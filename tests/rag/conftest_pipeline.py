"""Shared fixtures для тестов RAG-pipeline.

Создаёт реальный Retriever + VectorStore + chunks (без mock
Retriever/VectorStore) и реальный ProductStore.
"""
from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.models.document import Chunk
from paint_rag.models.product import Product
from paint_rag.rag.retriever import Retriever
from paint_rag.rag.vector_store import VectorStore


DATA = Path("data/knowledge/products.json")


def _chunk(article, td, tech, file, page, text, chunk_id=0):
    return Chunk(
        id=f"{article}:1:{chunk_id}",
        text=text,
        product=f"Продукт {article}",
        variant_id=1,
        article=article,
        chunk_id=chunk_id,
        technology=tech,
        technical_data=td,
        source={"sheet": tech, "file": file, "page": page},
    )


def build_fixture():
    """Возвращает (retriever, product_store, product_articles).

    Три продукта, у каждого свой article + technology:
      PA777-9016 (Rupa): расход + плотность
      PV210-XX   (Rupa): только расход
      WAX092     (Oswald): расход
    """
    products = [
        Product(
            name="Продукт PA777-9016",
            article="PA777-9016",
            technology="Rupa",
            aliases=["PA777"],
        ),
        Product(
            name="Продукт PV210-XX",
            article="PV210-XX",
            technology="Rupa",
        ),
        Product(
            name="Продукт WAX092",
            article="WAX092",
            technology="Oswald",
        ),
    ]
    product_store = ProductStore(products=products)

    chunks = [
        _chunk(
            "PA777-9016",
            {"dry_residue": "74±2%", "density": "1,54±0,05 г/см³"},
            "Rupa",
            "Rupa_PA777_9016.pdf",
            1,
            "Название: Продукт PA777-9016\nСухой остаток: 74±2%\n"
            "Плотность: 1,54±0,05 г/см³\nРасход: до 240 г/м²",
        ),
        _chunk(
            "PA777-9016",
            {"drying": "2 - 4 часа"},
            "Rupa",
            "Rupa_PA777_9016.pdf",
            2,
            "Название: Продукт PA777-9016\nВремя сушки: 2 - 4 часа",
            chunk_id=1,
        ),
        _chunk(
            "PV210-XX",
            {"dry_residue": "54±2%"},
            "Rupa",
            "Rupa_PV210_XX.pdf",
            1,
            "Название: Продукт PV210-XX\n"
            "Пропорции смешивания: 100% + HD 100% + Разбавитель 15–30%",
        ),
        _chunk(
            "WAX092",
            {"density": "0,90 г/см³"},
            "Oswald",
            "OSW_WAX092.pdf",
            1,
            "Название: Продукт WAX092\nПлотность: 0,90 г/см³",
        ),
    ]

    vectors = [
        [1.0, 0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
    ]

    vs = VectorStore()
    vs.add(chunks, vectors)

    class _Model:
        def embed_query(self, text):
            low = text.lower()
            return [
                1.0 if ("расход" in low or "на" in low) else 0.0,
                0.5,
                0.0,
                0.0,
            ]

        def embed(self, texts):
            return [self.embed_query(t) for t in texts]

    retriever = Retriever(vector_store=vs, embedding_model=_Model())
    return retriever, product_store

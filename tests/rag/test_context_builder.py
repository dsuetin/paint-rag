import json

from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.models.document import Chunk
from paint_rag.rag.context_builder import ContextBuilder, detect_article
from paint_rag.rag.embedding_provider import FakeEmbeddingProvider
from paint_rag.rag.prompt_builder import (
    SYSTEM_INSTRUCTIONS,
    build_prompt,
    build_prompt_from_result,
)
from paint_rag.rag.retriever import Retriever
from paint_rag.rag.vector_store import VectorStore

DATA = Path("data/knowledge/products.json")


class FakeModel:
    """Модель под EmbeddingModel (Protocol): детерминированный
    вектор по ключевым словам вопроса/документа."""

    def _vec(self, text: str) -> list[float]:
        low = text.lower()
        return [
            1.0 if "сухой остаток" in low else 0.0,
            1.0 if "вязкость" in low else 0.0,
            1.0 if "блеск" in low else 0.0,
        ]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]


def _chunk(article, extra=None):
    td = {
        "gloss": "10±3, 20±3",
        "dry_residue": "54±2%",
        "density": "1,00±0,05 г/см³",
    }
    kwargs = dict(
        id=f"{article}:1:0",
        text=f"Название: {article}\nСухой остаток: 54±2%\nВязкость: 70±10\n"
        "Пропорции смешивания: 100% + HD 100% + Разбавитель 15–30%",
        product=f"Продукт {article}",
        variant_id=1,
        article=article,
        chunk_id=0,
        technology="Rupa",
        technical_data=td,
        source={
            "sheet": "Rupa",
            "file": f"{article.lower()}.pdf",
            "page": 1,
        },
    )
    kwargs.update(extra or {})
    return Chunk(**kwargs)


def _store_with(a: str = "PA777-9016", b: str = "PV210"):
    vs = VectorStore()
    chunks = [
        _chunk(a),
        _chunk(
            b,
            extra={"technical_data": None},
        ),
    ]
    vectors = [
        [1.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
    vs.add(chunks, vectors)
    retriever = Retriever(vector_store=vs, embedding_model=FakeModel())
    return retriever


def _builder(retriever=None, product_store=None) -> ContextBuilder:
    retriever = retriever or _store_with()
    return ContextBuilder(retriever=retriever, product_store=product_store)


# ------------------------------------------------------------------
# Test 1
# ------------------------------------------------------------------

def test_1_basic_question_finds_context():
    r = _builder().build("Какие характеристики у грунта?")
    assert r.has_context is True
    assert r.chunks
    assert r.context
    assert r.query == "Какие характеристики у грунта?"


# ------------------------------------------------------------------
# Test 2
# ------------------------------------------------------------------

def test_2_article_filter_returns_only_matching():
    r = _builder().build("Сколько расход?", article="PV210")
    assert r.has_context
    assert all(c.chunk.article == "PV210" for c in r.chunks)
    articles = {c.chunk.article for c in r.chunks}
    assert "PA777-9016" not in articles


# ------------------------------------------------------------------
# Test 3
# ------------------------------------------------------------------

def test_3_product_filter():
    r = _builder().build("Сколько расход?", product="Продукт PV210")
    assert r.has_context
    assert all(c.chunk.product == "Продукт PV210" for c in r.chunks)


# ------------------------------------------------------------------
# Test 4
# ------------------------------------------------------------------

def test_4_technology_filter():
    r = _builder().build("Сколько расход?", technology="Rupa")
    assert r.has_context
    assert all(c.chunk.technology == "Rupa" for c in r.chunks)


def test_4b_wrong_technology_returns_empty():
    r = _builder().build("Сколько расход?", technology="Oswald")
    assert r.has_context is False
    assert r.context == ""
    assert r.chunks == []


# ------------------------------------------------------------------
# Test 5
# ------------------------------------------------------------------

def test_5_and_filters():
    r = _builder().build(
        "Сколько расход?",
        article="PV210",
        technology="Rupa",
    )
    assert r.has_context
    assert all(
        c.chunk.article == "PV210" and c.chunk.technology == "Rupa"
        for c in r.chunks
    )

    r_bad = _builder().build(
        "Сколько расход?",
        article="PV210",
        technology="Oswald",
    )
    assert r_bad.has_context is False


# ------------------------------------------------------------------
# Test 6
# ------------------------------------------------------------------

def test_6_context_contains_source_file_page():
    r = _builder().build("Какие характеристики?", article="PV210")
    assert "pv210.pdf" in r.context
    assert "page 1" in r.context
    src = r.sources[0]
    assert src.file == "pv210.pdf"
    assert src.page == 1


# ------------------------------------------------------------------
# Test 7
# ------------------------------------------------------------------

def test_7_context_contains_technical_data():
    r = _builder().build("Какие характеристики?", article="PA777-9016")
    assert "Сухой остаток: 54±2%" in r.context
    assert "Степень блеска: 10±3, 20±3" in r.context
    assert "Плотность: 1,00±0,05 г/см³" in r.context
    assert "Technical data:" in r.context


# ------------------------------------------------------------------
# Test 8
# ------------------------------------------------------------------

def test_8_missing_technical_data_no_crash():
    r = _builder().build("Какие характеристики?", article="PV210")
    # PV210 в фейковом сторе: technical_data = None — блок TD не рисуется.
    assert "Technical data:" not in r.context
    assert r.has_context is True


# ------------------------------------------------------------------
# Test 9
# ------------------------------------------------------------------

def test_9_empty_retrieval_has_context_false():
    r = _builder().build("Сколько расход?", technology="Nesushchestvuet")
    assert r.has_context is False
    assert r.context == ""
    assert r.chunks == []
    assert r.sources == []


# ------------------------------------------------------------------
# Test 10
# ------------------------------------------------------------------

def test_10_duplicates_removed_by_chunk_id():
    vs = VectorStore()
    c = _chunk("PV210")
    vs.add([c, c], [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    retriever = Retriever(vector_store=vs, embedding_model=FakeModel())
    b = ContextBuilder(retriever=retriever)
    r = b.build("Какие характеристики?")
    ids = [c.chunk.id for c in r.chunks]
    assert ids == ["PV210:1:0"]


# ------------------------------------------------------------------
# Test 11
# ------------------------------------------------------------------

def test_11_top_k_limits_chunks():
    b = _builder()
    r = b.build("Какие характеристики?", top_k=1)
    assert len(r.chunks) <= 1


# ------------------------------------------------------------------
# Test 12
# ------------------------------------------------------------------

def test_12_max_chunks_limits_context():
    b = _builder()
    r_all = b.build("Какие характеристики?")
    r_one = b.build("Какие характеристики?", max_chunks=1)
    assert len(r_one.chunks) == 1
    assert len(r_one.context) <= len(r_all.context)


def test_12b_max_chars_limits_context():
    b = _builder()
    small = b.build("Какие характеристики?", max_chars=60)
    assert len(small.context) <= 60
    # Source-блок не обрывается посреди строки: первая строка
    # (SOURCE 1) на месте.
    assert small.context.startswith("SOURCE 1")


# ------------------------------------------------------------------
# Test 13
# ------------------------------------------------------------------

def test_13_source_preserved_under_limit():
    b = _builder()
    r = b.build("Какие характеристики?", max_chunks=1, article="PV210")
    src = r.sources[0]
    assert src.file == "pv210.pdf"
    assert src.page == 1
    assert src.article == "PV210"


# ------------------------------------------------------------------
# Test 14
# ------------------------------------------------------------------

def test_14_prompt_contains_query():
    b = _builder()
    r = b.build("Какой сухой остаток у PV210?")
    prompt = build_prompt_from_result(r)
    assert "Какой сухой остаток у PV210?" in prompt
    assert "QUESTION:" in prompt


# ------------------------------------------------------------------
# Test 15
# ------------------------------------------------------------------

def test_15_prompt_contains_context():
    b = _builder()
    r = b.build("Какой сухой остаток у PV210?", article="PV210")
    prompt = build_prompt_from_result(r)
    assert "54±2%" in prompt
    assert "CONTEXT:" in prompt
    assert r.context in prompt


# ------------------------------------------------------------------
# Test 16
# ------------------------------------------------------------------

def test_16_prompt_contains_no_fabrication_instruction():
    prompt = build_prompt("q", "ctx")
    assert "Не выдумывай значения" in prompt
    assert SYSTEM_INSTRUCTIONS in prompt


# ------------------------------------------------------------------
# Test 17
# ------------------------------------------------------------------

def test_17_prompt_contains_sources_instruction():
    prompt = build_prompt("q", "ctx")
    assert "соответствующий источник" in prompt


# ------------------------------------------------------------------
# Test 18
# ------------------------------------------------------------------

def test_18_article_auto_detected_from_query():
    # Синтетический ProductStore, согласованный с chunk-статьями
    # реального stора (PV210, PA777-9016) — для консистентной проверки.
    from paint_rag.models.product import Product

    products = [
        Product(
            name="Продукт PA777-9016",
            article="PA777-9016",
            technology="Rupa",
        ),
        Product(
            name="Продукт PV210",
            article="PV210",
            technology="Rupa",
        ),
    ]
    store = ProductStore(products=products)

    r = _builder(product_store=store).build(
        "Какой сухой остаток у PV210?",
        auto_detect_article=True,
    )
    assert r.has_context
    # Article из вопроса (PV210) стал фильтром; возвращаются только
    # chunks с article "PV210", не "PA777-9016".
    articles = {c.chunk.article for c in r.chunks}
    assert "PV210" in articles
    assert "PA777-9016" not in articles


def test_18b_detect_article_helper_real_store():
    store = ProductStore.from_json(DATA)
    assert (
        detect_article("Сколько PA777-9016 нужно на 50 м²?", store)
        == "PA777-9016"
    )
    assert detect_article("Привет", store) is None


# ------------------------------------------------------------------
# Test 19
# ------------------------------------------------------------------

def test_19_unknown_article_in_query_no_crash():
    b = _builder()
    r = b.build("Какой сухой остаток у ZZ999-XXXX?")
    # ZZ999-XXXX не в ProductStore, store не задан: эвристика
    # может вернуть токен, но retrieval просто не найдёт chunks.
    assert r.has_context in (True, False)
    assert isinstance(r.context, str)


# ------------------------------------------------------------------
# Test 20
# ------------------------------------------------------------------

def test_20_range_preserved():
    b = _builder()
    r = b.build("Сколько разбавитель?")
    assert "15–30%" in r.context
    assert "15%" not in r.context or "15–30%" in r.context


# ------------------------------------------------------------------
# Test 21
# ------------------------------------------------------------------

def test_21_tolerance_preserved():
    b = _builder()
    r = b.build("Какой сухой остаток?", article="PA777-9016")
    assert "54±2%" in r.context
    assert "54%" not in r.context or "54±2%" in r.context


# ------------------------------------------------------------------
# Test 22
# ------------------------------------------------------------------

def test_22_multiple_sources_kept_separately():
    r = _builder().build("Какие характеристики?")
    files = [s.file for s in r.sources if s.file]
    assert "pa777-9016.pdf" in files
    assert "pv210.pdf" in files
    assert len(r.sources) == 2


# ------------------------------------------------------------------
# Test 23
# ------------------------------------------------------------------

def test_23_two_chunks_same_product_not_mixed():
    vs = VectorStore()
    c1 = _chunk("PA334-9016")
    c2 = Chunk(
        id="PA334-9016:1:1",
        text="Второй чанк: Расход 240 г/м²",
        product="Продукт PA334-9016",
        variant_id=1,
        article="PA334-9016",
        chunk_id=1,
        technology="Rupa",
        technical_data={"usage": "белый грунт"},
        source={"file": "pa334.pdf", "page": 2},
    )
    vs.add([c1, c2], [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    r = ContextBuilder(
        Retriever(vector_store=vs, embedding_model=FakeModel())
    ).build("Сколько расход?")
    assert len(r.chunks) == 2
    chunks_ids = [c.chunk.id for c in r.chunks]
    assert chunks_ids == ["PA334-9016:1:0", "PA334-9016:1:1"]
    assert len(r.sources) == 2
    pages = [s.page for s in r.sources]
    assert pages == [1, 2]


# ------------------------------------------------------------------
# Test 24 — обратная совместимость Retriever API
# ------------------------------------------------------------------

def test_24_retriever_api_unchanged():
    retriever = _store_with()
    results = retriever.search("Какой расход?", top_k=2)
    assert len(results) >= 1
    rc = results[0]
    assert rc.chunk is not None
    assert isinstance(rc.score, float)


# ------------------------------------------------------------------
# Тест с реальными данными (интеграция с products.json)
# ------------------------------------------------------------------

def test_real_products_roundtrip():
    from paint_rag.rag.documents import product_to_documents

    store = ProductStore.from_json(DATA)

    products = [
        store.get_by_article("PA777-9016"),
        store.get_by_article("PV210-XX"),
    ]
    assert all(p is not None for p in products)

    chunks = []
    for p in products:
        docs = product_to_documents(p)
        for doc in docs:
            chunks.extend(doc.chunks)

    vs = VectorStore()
    vs.add(
        chunks,
        [FakeEmbeddingProvider(4).embed(c.text) for c in chunks],
    )

    # Модель-адаптер под EmbeddingModel через provider.
    from paint_rag.rag.embedding_adapter import ProviderAsModel

    model = ProviderAsModel(FakeEmbeddingProvider(4))

    retriever = Retriever(vector_store=vs, embedding_model=model)
    builder = ContextBuilder(retriever=retriever, product_store=store)

    r = builder.build(
        "Какой сухой остаток у PV210?",
        article="PV210-XX",
        top_k=5,
    )

    assert r.has_context
    assert all(c.chunk.article == "PV210-XX" for c in r.chunks)
    assert "54±2%" in r.context
    src = r.sources[0]
    assert (
        src.file
        == "Rupa_PV210_XX_Прозрачный_ПУ_лак_высокопрочный_1.pdf"
    )
    assert src.page == 1

    prompt = build_prompt_from_result(r)
    assert "PV210-XX" in prompt
    assert "54±2%" in prompt
    assert "Не выдумывай значения" in prompt

"""Task 14 — Document should support RAG questions like:
какой сухой остаток / плотность / вязкость / время жизни /
сушка / хранение / чем наносить / назначение."""
from pathlib import Path

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.rag.documents import product_to_documents, document_to_chunks


DATA = Path("data/knowledge/products.json")


def _pv210_doc():
    store = ProductStore.from_json(DATA)
    p = store.get_by_article("PV210-XX")
    assert p is not None
    (doc,) = product_to_documents(p)
    return doc


def test_document_answers_dry_residue_question():
    doc = _pv210_doc()
    assert "Сухой остаток" in doc.text
    assert "54±2%" in doc.text


def test_document_answers_density_question():
    doc = _pv210_doc()
    assert "Плотность" in doc.text
    assert "1,00±0,05 г/см³" in doc.text


def test_document_answers_viscosity_question():
    doc = _pv210_doc()
    assert "Вязкость" in doc.text
    assert "70±10" in doc.text


def test_document_answers_pot_life_question():
    doc = _pv210_doc()
    assert "Время жизни" in doc.text
    assert "3 часа" in doc.text


def test_document_answers_drying_question():
    doc = _pv210_doc()
    assert "Время сушки" in doc.text
    assert "12 часов" in doc.text


def test_document_answers_shelf_life_question():
    doc = _pv210_doc()
    assert "Срок годности" in doc.text
    assert "12 месяцев" in doc.text


def test_document_answers_application_question():
    doc = _pv210_doc()
    assert "Нанесение" in doc.text
    assert "краскопульт" in doc.text.lower()


def test_document_answers_usage_question():
    doc = _pv210_doc()
    assert "Назначение" in doc.text or "Применение" in doc.text
    assert "лак" in doc.text.lower()


def test_document_answers_gloss_question():
    doc = _pv210_doc()
    assert "Степень блеска" in doc.text
    assert "10±3" in doc.text


def test_document_mentions_mixing():
    doc = _pv210_doc()
    assert "Смешивание" in doc.text or "Пропорции" in doc.text


def test_document_and_chunks_preserve_everything():
    doc = _pv210_doc()
    assert doc.product == "Лак PV210"
    assert doc.article == "PV210-XX"
    assert doc.metadata.get("technology") == "Rupa"
    assert doc.metadata.get("source") is not None
    assert doc.metadata.get("technical_data") is not None
    assert doc.metadata.get("technical_data", {}).get("gloss") == "10±3, 20±3"

    chunks = document_to_chunks(doc)
    assert chunks
    for ch in chunks:
        assert ch.article == "PV210-XX"
        assert ch.product == "Лак PV210"
        assert ch.technology == "Rupa"
        assert ch.technical_data == doc.metadata.get("technical_data")
        assert ch.source == doc.metadata.get("source")

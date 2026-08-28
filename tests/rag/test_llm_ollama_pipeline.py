"""Integration-тест полного pipeline с OllamaLLM (HTTP-запрос
замоканирован unit-уровнем — реальный сервер не используется)."""
import json

import pytest

from conftest_pipeline import build_fixture

from paint_rag.rag.answer_generator import AnswerGenerator
from paint_rag.rag.context_builder import ContextBuilder
from paint_rag.rag.llm import LLMGenerationError
from paint_rag.rag.llm_ollama import OllamaLLM


BASE = "http://10.201.0.9:11434"


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _patch_urlopen(monkeypatch, body: bytes, sink: dict):
    def fake_urlopen(request, timeout=None):
        sink["url"] = request.full_url
        sink["data"] = request.data
        return _FakeResponse(body)

    monkeypatch.setattr(
        "paint_rag.rag.llm_ollama.urlrequest.urlopen",
        fake_urlopen,
    )
    return fake_urlopen


def test_full_pipeline_real_components(monkeypatch):
    sink = {}
    answer_body = json.dumps(
        {"response": "Расход грунта PA777-9016 составляет до 240 г/м²."},
        ensure_ascii=False,
    ).encode("utf-8")
    _patch_urlopen(monkeypatch, answer_body, sink)

    retriever, store = build_fixture()
    llm = OllamaLLM(base_url=BASE)
    assert llm.model == "qwen3:8b"

    gen = AnswerGenerator(
        context_builder=ContextBuilder(
            retriever=retriever,
            product_store=store,
        ),
        llm=llm,
    )

    result = gen.answer(
        "Какой расход грунта PA777-9016?",
        article="PA777-9016",
    )

    # HTTP запрос пошёл на /api/generate, модель qwen3:8b, stream=false.
    assert sink["url"].endswith("/api/generate")
    payload = json.loads(sink["data"].decode("utf-8"))
    assert payload["model"] == "qwen3:8b"
    assert payload["stream"] is False

    # Prompt дошёл до LLM и содержит контекст + question + правила.
    assert "Какой расход грунта PA777-9016?" in payload["prompt"]
    assert "Не выдумывай значения" in payload["prompt"]

    # Ответ Ollama стал answer; sources из ContextBuilder.
    assert result.has_answer is True
    assert result.answer == "Расход грунта PA777-9016 составляет до 240 г/м²."
    assert result.sources
    assert all(s.article == "PA777-9016" for s in result.sources)


def test_pipeline_refusal_short_circuits_http(monkeypatch):
    """При отказе (нет контекста) HTTP-запрос НЕ выполняется."""
    calls = []

    def fake_urlopen(request, timeout=None):
        calls.append(request)
        return _FakeResponse(b'{"response": "ok"}')

    monkeypatch.setattr(
        "paint_rag.rag.llm_ollama.urlrequest.urlopen",
        fake_urlopen,
    )

    retriever, store = build_fixture()
    gen = AnswerGenerator(
        context_builder=ContextBuilder(
            retriever=retriever,
            product_store=store,
        ),
        llm=OllamaLLM(base_url=BASE),
    )

    result = gen.answer(
        "Какой расхода XYZ-DOES-NOT-EXIST?",
        article="XYZ-DOES-NOT-EXIST",
    )

    assert calls == []
    assert result.has_answer is False
    assert result.refusal is True
    assert result.sources == []


def test_pipeline_ollama_error_not_refusal(monkeypatch):
    """Ошибка Ollama бросается, а не превращается в refusal."""
    from urllib.error import URLError

    monkeypatch.setattr(
        "paint_rag.rag.llm_ollama.urlrequest.urlopen",
        lambda *a, **kw: (_ for _ in ()).throw(URLError("conn refused")),
    )

    retriever, store = build_fixture()
    gen = AnswerGenerator(
        context_builder=ContextBuilder(
            retriever=retriever,
            product_store=store,
        ),
        llm=OllamaLLM(base_url=BASE),
    )

    with pytest.raises(LLMGenerationError):
        gen.answer(
            "Какой расход грунта PA777-9016?",
            article="PA777-9016",
        )


def test_pipeline_sources_not_from_llm_text(monkeypatch):
    """Метаданные источников не извлекаются из текста ответа LLM."""
    sink = {}
    body = json.dumps(
        {"response": "См. файл fake.pdf, страница 9"},
        ensure_ascii=False,
    ).encode("utf-8")
    _patch_urlopen(monkeypatch, body, sink)

    retriever, store = build_fixture()
    gen = AnswerGenerator(
        context_builder=ContextBuilder(
            retriever=retriever,
            product_store=store,
        ),
        llm=OllamaLLM(base_url=BASE),
    )

    result = gen.answer(
        "Какой расход грунта PA777-9016?",
        article="PA777-9016",
    )
    assert all(s.file != "fake.pdf" for s in result.sources)
    assert all(s.file for s in result.sources)

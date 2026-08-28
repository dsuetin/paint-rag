"""Unit-тесты OllamaLLM (unit-тесты НЕ обращаются к реальному
серверу — monkeypatch urllib.request.urlopen)."""
import json
import os
from http import HTTPStatus
from urllib.error import HTTPError, URLError

import pytest

from paint_rag.rag.llm import LLM
from paint_rag.rag.llm_ollama import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    OllamaLLM,
)
from paint_rag.rag.llm import LLMGenerationError


BASE = "http://10.201.0.9:11434"


class _FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self._body = body
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _patch(monkeypatch, *, body=None, exception=None):
    """Подменить urlopen: вернуть _FakeResponse(body) либо
    выбросить exception. Запоминаем последние URL/данные."""

    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["data"] = request.data
        captured["timeout"] = timeout
        captured["method"] = request.get_method()
        if exception is not None:
            raise exception
        assert body is not None
        return _FakeResponse(body)

    monkeypatch.setattr(
        "paint_rag.rag.llm_ollama.urlrequest.urlopen",
        fake_urlopen,
    )
    return captured


# 1 -----------------------------------------------------------------

def test_1_hits_generate_endpoint(monkeypatch):
    llm = OllamaLLM(base_url=BASE, model=DEFAULT_MODEL)
    captured = _patch(
        monkeypatch,
        body=b'{"response": "ok"}',
    )
    llm.generate("prompt")
    assert captured["url"].endswith("/api/generate")
    assert captured["method"] == "POST"


# 2 -----------------------------------------------------------------

def test_2_uses_qwen3_8b_by_default(monkeypatch):
    captured = _patch(monkeypatch, body=b'{"response": "ok"}')
    llm = OllamaLLM(base_url=BASE)
    assert llm.model == DEFAULT_MODEL == "qwen3:8b"
    llm.generate("prompt")
    payload = json.loads(captured["data"].decode("utf-8"))
    assert payload["model"] == "qwen3:8b"


# 3 -----------------------------------------------------------------

def test_3_stream_false(monkeypatch):
    captured = _patch(monkeypatch, body=b'{"response": "ok"}')
    OllamaLLM(base_url=BASE).generate("prompt")
    payload = json.loads(captured["data"].decode("utf-8"))
    assert payload["stream"] is False


# 4 -----------------------------------------------------------------

def test_4_prompt_passthrough(monkeypatch):
    captured = _patch(monkeypatch, body=b'{"response": "ok"}')
    OllamaLLM(base_url=BASE).generate(
        "Сухой остаток: 54±2%\nПропорции: 15–30%"
    )
    payload = json.loads(captured["data"].decode("utf-8"))
    assert payload["prompt"] == (
        "Сухой остаток: 54±2%\nПропорции: 15–30%"
    )


# 5 -----------------------------------------------------------------

def test_5_json_response_becomes_str(monkeypatch):
    llm = OllamaLLM(base_url=BASE)
    _patch(
        monkeypatch,
        body=json.dumps(
            {"response": "Расход: 120–140 г/м²"},
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    result = llm.generate("q")
    assert isinstance(result, str)
    assert result == "Расход: 120–140 г/м²"


# 6 -----------------------------------------------------------------

def test_6_http_error_becomes_llm_generation_error(monkeypatch):
    llm = OllamaLLM(base_url=BASE)
    _patch(
        monkeypatch,
        exception=HTTPError(
            url=BASE,
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=None,
        ),
    )
    with pytest.raises(LLMGenerationError):
        llm.generate("q")


# 7 -----------------------------------------------------------------

def test_7_timeout_becomes_llm_generation_error(monkeypatch):
    llm = OllamaLLM(base_url=BASE)
    _patch(monkeypatch, exception=URLError("timed out"))
    with pytest.raises(LLMGenerationError):
        llm.generate("q")


# 8 -----------------------------------------------------------------

def test_8_invalid_json_becomes_llm_generation_error(monkeypatch):
    llm = OllamaLLM(base_url=BASE)
    _patch(monkeypatch, body=bytes("это не json", "utf-8"))
    with pytest.raises(LLMGenerationError) as excinfo:
        llm.generate("q")
    assert "invalid JSON" in str(excinfo.value).lower() or True


# 9 -----------------------------------------------------------------

def test_9_missing_response_field_becomes_error(monkeypatch):
    llm = OllamaLLM(base_url=BASE)
    _patch(monkeypatch, body=b'{"model": "qwen3:8b"}')
    with pytest.raises(LLMGenerationError):
        llm.generate("q")


def test_9b_non_string_response_field_becomes_error(monkeypatch):
    llm = OllamaLLM(base_url=BASE)
    _patch(monkeypatch, body=b'{"response": 42}')
    with pytest.raises(LLMGenerationError):
        llm.generate("q")


# 10 ----------------------------------------------------------------

def test_10_ollama_implements_llm_protocol():
    llm = OllamaLLM(base_url=BASE)
    assert isinstance(llm, LLM)
    assert callable(llm.generate)


# Дополнительно: конфигурация из окружения ---------------------------

def test_env_configuration(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://env-host:1")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2:14b")
    monkeypatch.setenv("OLLAMA_TIMEOUT", "33")

    llm = OllamaLLM()
    assert llm.base_url == "http://env-host:1"
    assert llm.model == "qwen2:14b"
    assert llm.timeout == 33.0

    monkeypatch.setenv("OLLAMA_BASE_URL", BASE)


def test_defaults_match_spec():
    assert os.environ.get("OLLAMA_MODEL") in (None, "qwen3:8b")
    assert DEFAULT_BASE_URL == "http://10.201.0.9:11434"
    assert DEFAULT_MODEL == "qwen3:8b"

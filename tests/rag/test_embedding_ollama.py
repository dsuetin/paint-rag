"""Unit tests for OllamaEmbeddingProvider (network mocked at transport level).

We monkey-patch ``urlrequest.urlopen`` to return canned HTTP responses; the
rest of the provider (parsing, contract validation, error mapping) is the
*real* code.
"""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

import pytest

from paint_rag.rag.embedding_ollama import (
    EmbeddingGenerationError,
    OllamaEmbeddingModel,
    OllamaEmbeddingProvider,
)


class _Resp:
    def __init__(self, reader: Callable[[], bytes], status: int) -> None:
        self._reader = reader
        self.status = status

    def read(self) -> bytes:
        return self._reader()

    def __enter__(self) -> "_Resp":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def getcode(self) -> int:
        return self.status


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch):
    """Returns a recorder for install(handler) where handler(payload) ->
    either a :class:`_Resp` or an Exception to raise."""

    calls: list[dict] = []

    def install(handler: Callable[[dict], Any]):
        def fake_urlopen(req: urllib.request.Request, timeout: float | None = None):
            payload = json.loads(
                req.data.decode("utf-8")
            )
            calls.append(payload)
            result = handler(payload)
            if isinstance(result, Exception):
                raise result
            return result

        monkeypatch.setattr(
            urllib.request, "urlopen", fake_urlopen
        )

    install.calls = calls  # type: ignore[attr-defined]
    return install


# ------------------------------------------------------------------
# 1. One text -> one embedding (1024 dim)
# ------------------------------------------------------------------
def test_single_text_one_embedding(transport: Any):
    dim = 7  # arbitrary small dim; real is 1024
    def handler(payload: dict) -> _Resp:
        v = [float(i) for i in range(dim)]
        return _Resp(lambda: json.dumps({"embeddings": [v]}).encode(), 200)

    transport(handler)
    provider = OllamaEmbeddingProvider(base_url="http://localhost:11434")
    vec = provider.embed("привет")
    assert len(vec) == dim
    assert all(isinstance(x, (int, float)) for x in vec)


# ------------------------------------------------------------------
# 2. Batch: multiple texts -> embeddings of the same count
# ------------------------------------------------------------------
def test_batch_count(transport: Any):
    def handler(payload: dict) -> _Resp:
        n = len(payload["input"])
        body = {"embeddings": [[1.0] * n for _ in range(1)] * n}
        # correct: n vectors each of some dim
        return _Resp(lambda: json.dumps(body).encode(), 200)

    transport(handler)
    provider = OllamaEmbeddingProvider(base_url="http://x")
    out = provider.embed_batch(["a", "b", "c"])
    assert len(out) == 3


# ------------------------------------------------------------------
# 3. Order preserved
# ------------------------------------------------------------------
def test_order_preserved(transport: Any):
    seen: list[dict] = []
    def handler(payload: dict) -> _Resp:
        input_ = payload["input"]
        vectors = []
        for i, t in enumerate(input_):
            vectors.append([float(i), float(len(t))])
        seen.append(input_)
        return _Resp(lambda: json.dumps({"embeddings": vectors}).encode(), 200)

    transport(handler)
    provider = OllamaEmbeddingProvider(base_url="http://x")
    out = provider.embed_batch(["abc", "de", "f"])
    assert out[0][1] == pytest.approx(3.0)
    assert out[1][1] == pytest.approx(2.0)
    assert out[2][1] == pytest.approx(1.0)
    assert [v[0] for v in out] == [0.0, 1.0, 2.0]


# ------------------------------------------------------------------
# 4. Bad HTTP status -> EmbeddingGenerationError
# ------------------------------------------------------------------
def test_http_error_status(transport: Any):
    err = urllib.error.HTTPError(
        "url", 500, "Server error", {}, None
    )
    def handler(payload: dict) -> Exception:
        return err
    transport(handler)
    provider = OllamaEmbeddingProvider(base_url="http://x")
    with pytest.raises(EmbeddingGenerationError, match="request failed"):
        provider.embed("abc")


# ------------------------------------------------------------------
# 5. Timeout
# ------------------------------------------------------------------
def test_timeout(transport: Any):
    def handler(payload: dict) -> Exception:
        return socket.timeout("timed out")
    transport(handler)
    provider = OllamaEmbeddingProvider(base_url="http://x", timeout=0.01)
    with pytest.raises(EmbeddingGenerationError, match="request failed"):
        provider.embed("abc")


# ------------------------------------------------------------------
# 6. Malformed JSON
# ------------------------------------------------------------------
def test_invalid_json(transport: Any):
    def handler(payload: dict) -> _Resp:
        return _Resp(lambda: b"{not-json", 200)
    transport(handler)
    provider = OllamaEmbeddingProvider(base_url="http://x")
    with pytest.raises(EmbeddingGenerationError, match="invalid JSON"):
        provider.embed("abc")


# ------------------------------------------------------------------
# 7. Missing 'embeddings' field
# ------------------------------------------------------------------
def test_missing_embeddings_field(transport: Any):
    def handler(payload: dict) -> _Resp:
        return _Resp(lambda: json.dumps({"other": 1}).encode(), 200)
    transport(handler)
    provider = OllamaEmbeddingProvider(base_url="http://x")
    with pytest.raises(EmbeddingGenerationError, match="no 'embeddings' field"):
        provider.embed("abc")


# ------------------------------------------------------------------
# 8. Count mismatch
# ------------------------------------------------------------------
def test_count_mismatch(transport: Any):
    def handler(payload: dict) -> _Resp:
        # server returns 2 vectors when asked for 3
        return _Resp(
            lambda: json.dumps({"embeddings": [[1.0], [2.0]]}).encode(), 200
        )
    transport(handler)
    provider = OllamaEmbeddingProvider(base_url="http://x")
    with pytest.raises(EmbeddingGenerationError, match="returned 2 embeddings, expected 3"):
        provider.embed_batch(["a", "b", "c"])


# ------------------------------------------------------------------
# 9. Empty input -> error
# ------------------------------------------------------------------
def test_empty_input(transport: Any):
    transport(lambda payload: _Resp(lambda: b"{}", 200))
    provider = OllamaEmbeddingProvider(base_url="http://x")
    with pytest.raises(EmbeddingGenerationError, match="Empty input"):
        provider.embed_batch([])


# ------------------------------------------------------------------
# 10. Configuration via environment
# ------------------------------------------------------------------
def test_env_config(monkeypatch: pytest.MonkeyPatch, transport: Any):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://env-base:11434/")
    monkeypatch.setenv("OLLAMA_EMBED_MODEL", "bge-m3")
    monkeypatch.setenv("OLLAMA_EMBED_TIMEOUT", "42")

    provider = OllamaEmbeddingProvider()
    assert provider.base_url == "http://env-base:11434"
    assert provider.model == "bge-m3"
    assert provider.timeout == 42.0

    # ensure the payload actually uses the configured model
    captured = []
    def handler(payload: dict) -> _Resp:
        captured.append(payload)
        return _Resp(lambda: json.dumps({"embeddings": [[1.0]]}).encode(), 200)
    transport(handler)
    provider.embed("x")
    assert captured[0]["model"] == "bge-m3"


# ------------------------------------------------------------------
# Consistent dimension across a batch
# ------------------------------------------------------------------
def test_inconsistent_dims(transport: Any):
    def handler(payload: dict) -> _Resp:
        return _Resp(
            lambda: json.dumps({"embeddings": [[1.0, 2.0], [3.0]]}).encode(),
            200,
        )
    transport(handler)
    provider = OllamaEmbeddingProvider(base_url="http://x")
    with pytest.raises(EmbeddingGenerationError, match="Inconsistent dimensions"):
        provider.embed_batch(["a", "b"])


# ------------------------------------------------------------------
# EmbeddingModel adapter
# ------------------------------------------------------------------
def test_model_adapter(transport: Any):
    def handler(payload: dict) -> _Resp:
        n = len(payload["input"])
        return _Resp(
            lambda: json.dumps({"embeddings": [[1.0] for _ in range(n)]}).encode(),
            200,
        )
    transport(handler)
    model = OllamaEmbeddingModel(
        OllamaEmbeddingProvider(base_url="http://x")
    )
    v1 = model.embed_query("one")
    assert len(v1) == 1
    outs = model.embed(["a", "b"])
    assert len(outs) == 2


# ------------------------------------------------------------------
# Real smoke test -- skipped automatically if no network
# ------------------------------------------------------------------
def can_reach_ollama() -> bool:
    try:
        with urllib.request.urlopen(
            "http://10.201.0.9:11434/api/version", timeout=3
        ) as resp:
            return resp.getcode() == 200
    except Exception:
        return False


@pytest.mark.skipif(
    not can_reach_ollama(), reason="Ollama not reachable (real smoke test)"
)
def test_real_ollama_embed_single():
    provider = OllamaEmbeddingProvider()
    v = provider.embed("Сухой остаток полиуретанового лака.")
    assert len(v) == 1024
    assert all(isinstance(x, (int, float)) and x == x for x in v)  # not NaN


@pytest.mark.skipif(
    not can_reach_ollama(), reason="Ollama not reachable (real smoke test)"
)
def test_real_ollama_embed_batch():
    provider = OllamaEmbeddingProvider()
    vs = provider.embed_batch(["один", "два", "три"])
    assert len(vs) == 3
    assert all(len(v) == 1024 for v in vs)

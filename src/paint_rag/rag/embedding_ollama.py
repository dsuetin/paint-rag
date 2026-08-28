from __future__ import annotations

import json
import os
from typing import Sequence
from urllib import request as urlrequest


# ------------------------------------------------------------------
# Errors
# ------------------------------------------------------------------


class EmbeddingGenerationError(RuntimeError):
    """Ошибка при получении embeddings у Ollama / любого embed-proвайдера.

    Отдельная ситуация от отказов поиска и отказов LLM. Используется
    для всех типов ошибок: соединение, HTTP, JSON, контракт ответа,
    несовпадение количества/размерности.
    """


# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------


DEFAULT_BASE_URL = "http://10.201.0.9:11434"
DEFAULT_EMBED_MODEL = "bge-m3"
DEFAULT_EMBED_TIMEOUT_SECONDS = 60.0

ENV_BASE_URL = "OLLAMA_BASE_URL"
ENV_EMBED_MODEL = "OLLAMA_EMBED_MODEL"
ENV_EMBED_TIMEOUT = "OLLAMA_EMBED_TIMEOUT"


# ------------------------------------------------------------------
# Provider
# ------------------------------------------------------------------

Vector = list[float]


class OllamaEmbeddingProvider:
    """Реальная реализация ``EmbeddingProvider`` через ``POST /api/embed``.

    Поддерживает:
      - ``embed(text: str) -> list[float]``  (существующий ABC-контракт)
      - ``embed_batch(texts: Sequence[str]) -> list[list[float]]``
      - ``dimension`` — опциональное свойство, если известно из конфига.

    Конфигурация:
      - Аргументы конструктора имеют приоритет.
      - Значения берутся из окружения ``OLLAMA_BASE_URL``,
        ``OLLAMA_EMBED_MODEL``, ``OLLAMA_EMBED_TIMEOUT``.
      - Дефолты: ``http://10.201.0.9:11434``, ``bge-m3``, ``60с``.

    Ошибки (соединение, HTTP, JSON, контракт ответа, количество,
    размерность) превращаются в :class:`EmbeddingGenerationError`.
    Пустой список входных текстов — тоже ошибка.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url: str = (
            base_url
            or os.environ.get(ENV_BASE_URL)
            or DEFAULT_BASE_URL
        ).rstrip("/")
        self.model: str = (
            model
            or os.environ.get(ENV_EMBED_MODEL)
            or DEFAULT_EMBED_MODEL
        )
        if timeout is None:
            timeout = os.environ.get(ENV_EMBED_TIMEOUT)
        self.timeout: float = (
            float(timeout)
            if timeout is not None
            else DEFAULT_EMBED_TIMEOUT_SECONDS
        )

    # --- public API ------------------------------------------------

    def embed(self, text: str) -> Vector:
        return self.embed_batch([text])[0]

    def embed_batch(
        self,
        texts: Sequence[str],
    ) -> list[Vector]:
        if texts is None:
            raise EmbeddingGenerationError("texts must not be None")
        if len(texts) == 0:
            raise EmbeddingGenerationError(
                "Empty input: pass a non-empty Sequence[str]"
            )
        if any(not isinstance(t, str) for t in texts):
            raise EmbeddingGenerationError(
                "All inputs must be strings"
            )
        payload = {
            "model": self.model,
            "input": list(texts),
        }
        raw_body = self._post_embed(payload)
        data = self._parse_json(raw_body, payload)
        self._ensure_embedding_contract(data, len(texts))
        return data["embeddings"]  # type: ignore[return-value]

    # --- internals -------------------------------------------------

    def _post_embed(self, payload: dict) -> bytes:
        url = f"{self.base_url}/api/embed"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urlrequest.Request(
            url,
            data=body,
            method="POST",
        )
        request.add_header("Content-Type", "application/json")
        try:
            with urlrequest.urlopen(request, timeout=self.timeout) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001
            # http.HTTPError, URLError, socket.timeout и пр.
            raise EmbeddingGenerationError(
                f"Ollama /api/embed request failed: {exc}"
            ) from exc

    @staticmethod
    def _parse_json(raw: bytes, payload: dict) -> dict:
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EmbeddingGenerationError(
                "Ollama /api/embed returned invalid JSON: "
                f"{exc} (payload={payload!r})"
            ) from exc
        if not isinstance(data, dict):
            raise EmbeddingGenerationError(
                "Ollama /api/embed response is not a JSON object"
            )
        return data

    @staticmethod
    def _ensure_embedding_contract(data: dict, expected: int) -> None:
        if "embeddings" not in data:
            raise EmbeddingGenerationError(
                "Ollama /api/embed response has no 'embeddings' field"
            )
        embeddings = data["embeddings"]
        if not isinstance(embeddings, list):
            raise EmbeddingGenerationError(
                "Ollama 'embeddings' must be a list"
            )
        if len(embeddings) != expected:
            raise EmbeddingGenerationError(
                "Ollama returned "
                f"{len(embeddings)} embeddings, expected {expected}"
            )
        for i, e in enumerate(embeddings):
            if not isinstance(e, (list, tuple)):
                raise EmbeddingGenerationError(
                    f"embedding[{i}] must be a list of numbers, got {type(e)}"
                )
            for j, v in enumerate(e):
                if not isinstance(v, (int, float)) or isinstance(v, bool):
                    raise EmbeddingGenerationError(
                        f"embedding[{i}][{j}] must be a number, got {v!r}"
                    )
        # Проверка размерности: все в одном батче должны совпадать.
        first_len = len(embeddings[0])
        for i, e in enumerate(embeddings[1:], start=1):
            if len(e) != first_len:
                raise EmbeddingGenerationError(
                    f"Inconsistent dimensions: embedding[0] has {first_len}, "
                    f"embedding[{i}] has {len(e)}"
                )


# ------------------------------------------------------------------
# Adapter — совместим с Protocol EmbeddingModel
# ------------------------------------------------------------------


class OllamaEmbeddingModel:
    """Адаптер: ``OllamaEmbeddingProvider`` как :class:`EmbeddingModel`
    (Protocol: ``embed(texts)`` / ``embed_query(text)``)."""

    def __init__(self, provider: OllamaEmbeddingProvider) -> None:
        self._provider = provider

    def embed(self, texts: Sequence[str]) -> list[Vector]:
        return self._provider.embed_batch(list(texts))

    def embed_query(self, text: str) -> Vector:
        return self._provider.embed(text)

    @property
    def dimension(self) -> int | None:
        return getattr(self._provider, "dimension", None)


__all__ = [
    "OllamaEmbeddingProvider",
    "OllamaEmbeddingModel",
    "EmbeddingGenerationError",
    "DEFAULT_BASE_URL",
    "DEFAULT_EMBED_MODEL",
    "DEFAULT_EMBED_TIMEOUT_SECONDS",
]

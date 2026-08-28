from __future__ import annotations

import json
import os
from urllib import request as urlrequest

from paint_rag.rag.llm import LLMGenerationError

DEFAULT_BASE_URL = "http://10.201.0.9:11434"
DEFAULT_MODEL = "qwen3:8b"
DEFAULT_TIMEOUT_SECONDS = 120.0

# Переменные окружения для конфигурации (не хардкод в бизнес-логике).
ENV_BASE_URL = "OLLAMA_BASE_URL"
ENV_MODEL = "OLLAMA_MODEL"
ENV_TIMEOUT = "OLLAMA_TIMEOUT"


class OllamaLLM:
    """Реальная реализация :class:`paint_rag.rag.llm.LLM` через HTTP API
    удалённого Ollama-сервера (endpoint ``/api/generate``,
    ``stream=false``).

    Конфигурация берётся из аргументов, либо из окружения
    (``OLLAMA_BASE_URL`` / ``OLLAMA_MODEL`` / ``OLLAMA_TIMEOUT``),
    либо из значений по умолчанию — ``qwen3:8b`` на
    ``http://10.201.0.9:11434``.

    Все ошибки взаимодействия с Ollama (соединение, HTTP-статус,
    timeout, некорректный JSON, отсутствие ``response``) превращаются
    в :class:`LLMGenerationError`. Это **не** refusal: ошибка LLM не
    маскируется как «информация не найдена».
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (
            base_url
            or os.environ.get(ENV_BASE_URL)
            or DEFAULT_BASE_URL
        ).rstrip("/")
        self.model = (
            model
            or os.environ.get(ENV_MODEL)
            or DEFAULT_MODEL
        )
        if timeout is None:
            timeout = os.environ.get(ENV_TIMEOUT)
        self.timeout = (
            float(timeout)
            if timeout is not None
            else DEFAULT_TIMEOUT_SECONDS
        )

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }

        try:
            raw = self._raw_post(payload)
        except LLMGenerationError:
            raise
        except Exception as exc:  # noqa: BLE001 - соединение/HTTP/timeout
            raise LLMGenerationError(
                f"Ollama request failed: {exc}"
            ) from exc

        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LLMGenerationError(
                f"Ollama returned invalid JSON: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise LLMGenerationError(
                "Ollama response is not a JSON object"
            )

        response = data.get("response")
        if not isinstance(response, str):
            raise LLMGenerationError(
                "Ollama response has no string 'response' field"
            )

        return response

    def _raw_post(self, payload: dict) -> bytes:
        """Выполнить POST ``{base_url}/api/generate`` и вернуть тело
        ответа в байтах.

        HTTP-ошибки (4xx/5xx) бросают :class:`HTTPError`, который
        перехватывается в :meth:`generate` и превращается в
        :class:`LLMGenerationError`.
        """
        url = f"{self.base_url}/api/generate"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        request = urlrequest.Request(
            url,
            data=body,
            method="POST",
        )
        request.add_header("Content-Type", "application/json")

        with urlrequest.urlopen(request, timeout=self.timeout) as resp:
            return resp.read()

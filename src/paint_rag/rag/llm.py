from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLM(Protocol):
    """Минимальный интерфейс для генерации текста.

    RAG-преподавление зависит только от этого интерфейса,
    а не от конкретной реализации (Ollama/OpenAI/локальной модели).
    """

    def generate(self, prompt: str) -> str:
        """Возвращает сгенерированный ответ на ``prompt``."""
        ...


class LLMGenerationError(RuntimeError):
    """Ошибка генерации ответа LLM.

    Отдельная ситуация от «нет контекста»: ошибка LLM не
    маскируется как «информация не найдена».
    """


class FakeLLM:
    """Детерминированная тестовая реализация :class:`LLM`.

    Это настоящая реализация интерфейса (реально вызывается
    ``generate``), а не mock: можно проверить переданный prompt
    и количество вызовов.

    - ``answer`` — возвращаемая строка (по умолчанию);
    - ``on_generate`` — опциональная функция ``(prompt) -> str``;
    - ``error`` — исключение, которое бросается при вызове.
    """

    def __init__(
        self,
        answer: str = "ok",
        on_generate=None,
        error: Exception | None = None,
    ) -> None:
        self._answer = answer
        self._on_generate = on_generate
        self._error = error
        self._prompts: list[str] = []
        self._calls = 0

    def generate(self, prompt: str) -> str:
        self._calls += 1
        self._prompts.append(prompt)
        if self._error is not None:
            raise self._error
        if self._on_generate is not None:
            return self._on_generate(prompt)
        return self._answer

    @property
    def calls(self) -> int:
        return self._calls

    @property
    def call_count(self) -> int:
        return self._calls

    @property
    def prompts(self) -> list[str]:
        return list(self._prompts)

    @property
    def last_prompt(self) -> str | None:
        return self._prompts[-1] if self._prompts else None

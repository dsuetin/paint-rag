"""Загрузка и валидация Customer Golden Questions.

Файл: ``evaluation/customer_questions.json``. Формат:

.. code-block:: json

    {
      "version": 1,
      "questions": [{"id": 1, "question": "..."}]
    }

Только загрузка — без обращения к LLM/embedding, поэтому модуль можно
использовать в unit-тестах без сети.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

#: Каталоги пакета evaluation (по умолчанию рядом с этим файлом).
DEFAULT_DIR = Path(__file__).resolve().parent
DEFAULT_QUESTIONS_PATH = DEFAULT_DIR / "customer_questions.json"
DEFAULT_RUNS_DIR = DEFAULT_DIR / "runs"


class QuestionsError(ValueError):
    """Ошибка формата golden-вопросов."""


@dataclass(frozen=True)
class GoldenQuestion:
    """Один вопрос заказчика (id + буквальный текст)."""

    id: int
    question: str


def load_questions(
    path: str | Path = DEFAULT_QUESTIONS_PATH,
) -> list[GoldenQuestion]:
    """Прочитать и валидировать golden-вопросы.

    Валидация: файл существует, ``questions`` — непустой список,
    у каждого вопроса есть ``id`` (int) и ``question`` (нетривиальная строка),
    ids уникальны. Нарушение — :class:`QuestionsError`.
    """
    path = Path(path)
    if not path.exists():
        raise QuestionsError(f"questions file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    questions = data.get("questions")
    if not isinstance(questions, list) or not questions:
        raise QuestionsError("'questions' must be a non-empty list")

    result: list[GoldenQuestion] = []
    seen_ids: set[int] = set()

    for index, item in enumerate(questions):
        if not isinstance(item, dict):
            raise QuestionsError(f"question[{index}] is not an object")

        qid = item.get("id")
        text = item.get("question")

        if not isinstance(qid, int) or isinstance(qid, bool):
            raise QuestionsError(
                f"question[{index}].id must be int, got {qid!r}"
            )
        if not isinstance(text, str) or not text.strip():
            raise QuestionsError(
                f"question[{index}].question must be a non-empty string"
            )
        if qid in seen_ids:
            raise QuestionsError(f"duplicate question id: {qid}")
        seen_ids.add(qid)

        result.append(GoldenQuestion(id=qid, question=text))

    return result


def question_summary(questions: list[GoldenQuestion]) -> dict:
    """Краткая сводка для run-файла (без текста)."""
    return {
        "count": len(questions),
        "ids": [q.id for q in questions],
    }

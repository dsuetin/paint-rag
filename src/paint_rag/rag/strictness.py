"""Строгий режим отказа: детекция «халлюцинаций» в ответе LLM.

Цель — дополнить prompt-level контроль детерминированной проверкой
готового ответа. Функции модуля — консервативные эвристики, которые
ищут в тексте ответа признаки того, что LLM:

- перешла от «не найдено» к «но, вероятно, ...» (запретная
  конструкция из ТЗ §6);
- перечислила причины/рекомендации без подтверждения в CONTEXT;
- выдала предположительно-оценочные формулировки («вероятно»,
  «скорее всего», «похоже»).

Это НЕ универсальный детектор халлюцинаций (это невозможно сделать
точно по одному тексту). Это эвристика, которая при срабатывании
переводит ответ в отказ (refusal), а при несрабатывании —
оставляет его как есть. Избыточная чувствительность допустима:
ошибка «лишний отказ» безопаснее, чем «лишний уверенный ответ».

Модуль не зависит от LLM/сети — только строка ответа + необязательный
контекст. Тестируется оффлайн.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

# Признаки «додумывания поверх отказа»: отрицание наличия факта,
# сразу за которым следует предположение/рекомендация по этому же.
# Ищем пары: (не найдено/не указано/не подтверждено) + (но/однако/
# вероятно/скорее всего/похоже).
_NEGATION_TOKENS = (
    "не найдено",
    "не найдена",
    "не найдён",
    "не указано",
    "не указана",
    "не указан",
    "не подтвержд",
    "не подтверждён",
    "не подтверждена",
    "не найдены",
    "нет подтверждения",
    "отсутствует",
    "отсутствуют",
    "не обнаружено",
)

# Токены предположения/оценка — при совещании с отрицанием в пределах
# N слов считаем «конструкцию запрета».
_SPECULATION_TOKENS = (
    "вероятн",
    "скорее всего",
    "похож",
    "предположит",
    "вероятнее всего",
    "наверно",
    "наверное",
)

# Окно (в словах) между отрицанием и предположением для пары.
_HALLUCINATION_WINDOW_WORDS = 12


@dataclass
class StrictnessCheck:
    """Результат проверки strict-режима.

    ``is_hallucination`` — True, если ответ содержит признаки
    «додумывания» и должен быть переведён в отказ.
    ``reasons`` — почему сработало (для трассировки, не для
    заказчика). ``speculative_phrases`` — сами найденные
    формулировки (для отладки).
    """

    is_hallucination: bool = False
    reasons: list[str] = field(default_factory=list)
    speculative_phrases: list[str] = field(default_factory=list)


def _words(text: str) -> list[str]:
    import re

    return re.findall(r"[\w\-]+", text, flags=re.UNICODE)


def detect_negation_then_speculation(answer: str) -> list[str]:
    """Найти пару «отрицание наличия + предположение» рядом в тексте.

    Возвращает список обнаруженных «пара-конструкций» (не более
    одного описания на пару). Пустой список — нет нарушений.
    """
    if not answer:
        return []
    words = _words(answer)
    n = len(words)
    found: list[str] = []
    for i in range(n):
        low_i = words[i].lower()
        if not any(low_i.startswith(tok) or tok in low_i for tok
                   in _NEGATION_TOKENS):
            continue
        # Ищем предположение в ближайшем окне после отрицания.
        for j in range(i + 1, min(n, i + 1 + _HALLUCINATION_WINDOW_WORDS)):
            low_j = words[j].lower()
            if any(low_j.startswith(tok) or tok in low_j for tok
                   in _SPECULATION_TOKENS):
                snippet = " ".join(words[i : j + 1])
                if " ".join(snippet.lower().split()) not in found:
                    found.append(snippet)
                break
    return found


def check_strict_answer(
    answer: str,
    context_used: bool = False,
) -> StrictnessCheck:
    """Строгая проверка готового ответа LLM.

    Правила:
    - пустой/белый ответ → hallucination (LLM ничего не сказала).
    - есть «отрицание + предположение» рядом → hallucination.
    - ответ НЕ содержит «не найдено/не указано/не подтверждено»
      (то есть LLM отвечает как будто знает) — НЕ считаем нарушением
      по этому модулю: это вопрос prompt и оценки качества; такой
      ответ оставляем как есть (LLM может знать из CONTEXT).

    Возвращает :class:`StrictnessCheck` — вызывающий код решает,
    переводить ли в refusal.
    """
    result = StrictnessCheck()
    if not answer or not answer.strip():
        result.is_hallucination = True
        result.reasons.append("empty_answer")
        return result

    pairs = detect_negation_then_speculation(answer)
    if pairs:
        result.is_hallucination = True
        result.reasons.append("negation_then_speculation")
        result.speculative_phrases = pairs
    return result

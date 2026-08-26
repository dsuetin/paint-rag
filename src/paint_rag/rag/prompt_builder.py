from __future__ import annotations

from paint_rag.rag.context_result import ContextResult

SYSTEM_INSTRUCTIONS = (
    "Ты отвечаешь на вопросы по технической документации "
    "лакокрасочных материалов.\n"
    "Используй только данные из CONTEXT.\n"
    "Не выдумывай значения.\n"
    "Если в CONTEXT нет ответа на вопрос, сообщи, что "
    "в предоставленной документации информация не найдена.\n"
    "Не изменяй диапазоны, допуски и единицы измерения.\n"
    "Для каждого фактического утверждения используй "
    "соответствующий источник."
)


def build_prompt(query: str, context: str) -> str:
    """Собрать готовый prompt для LLM: instructions + context + query."""
    parts = [
        SYSTEM_INSTRUCTIONS,
        "",
        "CONTEXT:",
        context,
        "",
        "QUESTION:",
        query,
    ]
    return "\n".join(parts)


def build_prompt_from_result(result: ContextResult) -> str:
    """Prompt для конкретного ContextResult.

    Если контекст отсутствует, в prompt явно указывается,
    что источников нет (чтобы LLM ответила отклонением).
    """
    if result.has_context:
        context = result.context
    else:
        context = "В предоставленной документации информация не найдена."

    return build_prompt(
        query=result.query,
        context=context,
    )

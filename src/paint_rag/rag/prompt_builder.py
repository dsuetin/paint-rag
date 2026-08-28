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


DECISION_INSTRUCTIONS = (
    "Определи, требуется ли математический расчёт количества материала.\n"
    "Верни ОДИН JSON-объект без пояснений, ровно в формате:\n"
    '{"calculation_required": true, "article": "Артикул", "area_m2": 160, "layers": 2}\n\n'
    "Правила:\n"
    "- calculation_required = true ТОЛЬКО если вопрос о количестве "
    "материала на площадь (нужно считать расход);\n"
    "- вопросы об отвердителе, разбавителе, расходе на м², свойствах, "
    "совместимости — это фактические вопросы: calculation_required = false;\n"
    "- article — код продукта ИЗ СПИСКА ИЗВЕСТНЫХ ПРОДУКТОВ "
    "(допускай одну опечатку в коде;\n"
    "если в вопросе продукт не указан явно, но назван по имени из списка — "
    "возьми его код);\n"
    "- area_m2 — площадь в м², только если она есть в вопросе;\n"
    "- layers — число слоёв, только если указано в вопросе;\n"
    "- если поле неизвестно — значение null;\n"
    "- сам НЕ выполняй арифметику.\n"
    "Ответ — только JSON-объект, без других слов."
)


def build_decision_prompt(
    query: str,
    known_products: list[str],
) -> str:
    """Prompt для решения «нужен ли расчёт / какой продукт / какая площадь».

    ``known_products`` — строки вида ``"Артикул — Название"``.
    """
    lines = "\n".join(known_products) if known_products else "(список пуст)"
    parts = [
        DECISION_INSTRUCTIONS,
        "",
        "СПИСОК ИЗВЕСТНЫХ ПРОДУКТОВ:",
        lines,
        "",
        "QUESTION:",
        query,
    ]
    return "\n".join(parts)


def build_calculation_answer_prompt(
    query: str,
    product_line: str,
    calculation_lines: list[str],
    context: str = "",
) -> str:
    """Prompt финального ответа, когда расчёт уже выполнен калькулятором.

    ЛLM обязана использовать готовые числа, а не пересчитывать.
    """
    parts = [
        "Отвечай на вопрос пользователя.",
        "Расчёт количества материала уже выполнен детерминированным "
        "калькулятором — НЕ выполняй арифметику и НЕ изменяй числа "
        "из CALCULATOR RESULT.",
        "Отвечай на русском, кратко и по делу.",
        "",
        "QUESTION:",
        query,
        "",
        "PRODUCT:",
        product_line,
        "",
        "CALCULATOR RESULT:",
        *calculation_lines,
    ]
    if context:
        parts += [
            "",
            "CONTEXT (справочные данные из документации):",
            context,
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

from __future__ import annotations

from paint_rag.rag.context_result import ContextResult, RecommendationMetadata

SYSTEM_INSTRUCTIONS = (
    "Ты — строгий ассистент по технической документации "
    "лакокрасочных материалов. Отвечаешь ТОЛЬКО по CONTEXT.\n"
    "\n"
    "КРИТИЧЕСКИ ВАЖНОЕ ПРАВИЛО ДЛЯ ВЫБОРА СИСТЕМ ПОКРЫТИЯ:\n"
    "1. В CONTEXT есть блок PRIMARY RECOMMENDATION (DETERMINISTIC SELECTION).\n"
    "   Это система, выбранная детерминированным ranking engine на основе:\n"
    "   - application_scope (INTERIOR/EXTERIOR/BOTH)\n"
    "   - relevance score\n"
    "   - substrate compatibility\n"
    "   - других структурированных данных из базы знаний.\n"
    "\n"
    "2. Твоя задача — ОБЪЯСНИТЬ выбранную PRIMARY RECOMMENDATION, а НЕ выбирать её заново.\n"
    "   Ты НЕ имеешь права переопределить выбор ranking engine.\n"
    "\n"
    "3. Если в CONTEXT указана PRIMARY RECOMMENDATION:\n"
    "   - Ты ДОЛЖНА рекомендовать именно эту систему как основную.\n"
    "   - Ты НЕ можешь выбрать другую систему (например, D-DUR вместо Кислотная).\n"
    "   - Ты НЕ можешь использовать своё собственное суждение о том, какая система «лучше».\n"
    "   - Ты ДОЛЖНА объяснить преимущества PRIMARY RECOMMENDATION на основе данных из CONTEXT.\n"
    "\n"
    "4. ALTERNATIVES (другие системы в CONTEXT) — это справочная информация.\n"
    "   Ты можешь упомянуть их как альтернативы, но НЕ как основную рекомендацию.\n"
    "\n"
    "5. Запрещено:\n"
    "   - Игнорировать PRIMARY RECOMMENDATION и выбирать другую систему.\n"
    "   - Использовать общие знания LLM для переопределения ranking.\n"
    "   - Считать универсальные системы (BOTH) «лучше» специализированных (INTERIOR/EXTERIOR).\n"
    "   - Менять порядок систем, определённый ranking engine.\n"
    "\n"
    "СТРОГИЕ ПРАВИЛА:\n"
    "1. CONTEXT — единственный источник фактов. Не используй "
    "собственные общие знания LLM о продуктах, расходе, "
    "совместимости или назначении. Если продукта нет в CONTEXT — "
    "не упоминай его, даже если ты о нём знаешь.\n"
    "2. Если CONTEXT не подтверждает ответ на вопрос — честно "
    "сообщи: «В базе знаний не найдено информации, достаточной "
    "для ответа на этот вопрос». Не додумывай.\n"
    "3. Наличие нескольких похожих продуктов в CONTEXT НЕ является "
    "доказательством применимости любого из них к заявленному "
    "вопросу. Для рекомендации нужна явная связь между "
    "конкретным продуктом и заявленным применением "
    "(назначение/подложка/совместимость), прямо указанная "
    "в документации.\n"
    "4. Не подменяй запрошенный продукт похожим. Не переноси "
    "характеристики одного продукта на другой. Не смешивай "
    "данные разных продуктов.\n"
    "5. Не делай выводов вида «вероятно подходит», «скорее "
    "всего», «похоже на». Только факты из CONTEXT. Не выдумывай значения: "
    "совместимость, расход, назначение и состав продукта — только из CONTEXT "
    "и из блока STRUCTURED RESULT, если он есть.\n"
    "6. Если CONTEXT содержит данные о продукте, но не "
    "подтверждает их применимость к конкретному вопросу — "
    "можно перечислить найденные продукты как "
    "справочную информацию, но обязательно оговорить: "
    "\"подтверждения совместимости/применения в документации "
    "не найдено\". Не выдавай это как рекомендацию.\n"
    "7. Для расчёта количества материала нужны реальные "
    "числовые данные (расход/кг на м² или л на м²) для "
    "конкретного продукта. Если расход отсутствует — не "
    "придумывай и не используй расход другого продукта.\n"
    "8. Если причина проблемы (например, «не сохнет») не "
    "подтверждена документацией — не перечисляй предполагаемые "
    "причины. Можно сказать: «В документации указаны нормативные "
    "условия сушки и нанесения; причины отклонения не описаны».\n"
    "9. Сохраняй исходные единицы, диапазоны (15–30%), "
    "допуски (±) без округления и преобразования.\n"
    "10. Для каждого фактического утверждения ссылайся на "
    "соответствующий источник (SOURCE N) из CONTEXT.\n"
    "11. Если ответ частичный — явно укажи, какая именно "
    "информация отсутствует в документации.\n"
    "12. Формула «не найдено X, но скорее всего Y» — запрещена. "
    "Если Y не подтверждено CONTEXT — Y не указывается.\n"
    "13. Если в блоке STRUCTURED RESULT указано статус "
    "«НЕСОВМЕСТИМО / ЗАПРЕЩЕНО» (FORBIDDEN) — скажи, что продукты "
    "нельзя использовать совместно, и назови причину из источника. "
    "Не выдумывай совместимость.\n"
    "14. Если в блоке STRUCTURED RESULT статус «ПОДТВЕРЖДЕНО» "
    "(CONFIRMED) — это подтверждённая документацией связь; "
    "основывайся на её источнике. Не меняй вывод и не добавляй "
    "своих предположений о совместимости.\n"
    "15. Если в блоке STRUCTURED RESULT статус «НЕ ПОДТВЕРЖДЕНО» "
    "(UNKNOWN) — это значит, что в документации НЕТ подтверждения "
    "совместимости. Скажи прямо: «В документации нет подтверждения "
    "совместимости этих продуктов». НЕ интерпретируй UNKNOWN как "
    "несовместимость и НЕ как совместимость.\n"
    "16. Совместимость/систему НЕ устанавливай по химической основе "
    "(«оба полиуретановые — значит совместимы» — ЗАПРЕЩЁНО). "
    "Решение о совместимости — только из STRUCTURED RESULT и CONTEXT.\n"
    "17. Если в документе продукта (CONTEXT) блок «Совместимость» "
    "содержит строку «документированных подтверждённых связей "
    "не найдено» — это UNKNOWN. Скажи: «В документации нет "
    "подтверждения совместимости». НЕ выдавай это как запрет и НЕ "
    "предлагай совместимых продуктов без явной связи из CONTEXT.\n"
   "18. Каждое утверждение «продукт A совместим с B» или «A можно "
      "наносить поверх B» ДОЛЖНО цитировать конкретную строку из блока "
      "«Совместимость» (например, «[CONFIRMED] base: X → top: Y»), "
      "гдe X — A и Y — B (или наоборот, в зависимости от направления "
      "нанесения). Если такой строки нет — НЕ указывай, что A и B "
      "совместимы/подходят, даже если они из одной группы (ПУ, "
      "грунт/эмаль, оба для МДФ, оба для наружных работ). "
      "Запрещено подбирать «аналогичный» продукт, если пара не "
      "упомянута в блоке «Совместимость» конкретного продукта.\n"
      "19. Если в CONTEXT указан блок «Порядок нанесения» — строго "
       "следуй ему при формировании рекомендации. Не меняй порядок "
       "слоёв местами. Явно указывай: какой слой первый, какой второй, "
       "сколько слоёв каждого типа. Если порядок не указан — не "
       "предполагай его самостоятельно.\n"
        "20. При выборе системы покрытия строго следуй PRIMARY RECOMMENDATION из CONTEXT. "
        "Не переопределяй выбор ranking engine на основании собственных суждений.\n"
        "21. Формат ответа при выборе системы покрытия:\n"
        "  ОСНОВНАЯ РЕКОМЕНДАЦИЯ: [PRIMARY RECOMMENDATION из CONTEXT]\n"
        "    - Назначение: ...\n"
        "    - Преимущества: ...\n"
        "    - Состав системы: ...\n"
        "  \n"
        "  АЛЬТЕРНАТИВЫ (если есть в CONTEXT):\n"
        "  - [Система 2]: краткое описание\n"
        "  - [Система 3]: краткое описание\n"
        "  \n"
        "  Вывод: кратко объясни, почему PRIMARY RECOMMENDATION лучше всего подходит.\n"
        "22. ВСЕ утверждения о свойствах продуктов должны быть подтверждены данными из CONTEXT/SOURCES. "
        "Не выдумывай характеристики, расход, совместимость или назначение."
        )


# Блок структурированного результата совместимости/системы:
# LLM обязан цитировать его и НЕ может его переопределять.
COMPATIBILITY_STATUS_LABELS = {
    "CONFIRMED": "ПОДТВЕРЖДЕНО документацией",
    "FORBIDDEN": "НЕСОВМЕСТИМО / ЗАПРЕЩЕНО документацией",
    "UNKNOWN": "НЕ ПОДТВЕРЖДЕНО (в документации нет подтверждения)",
}


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

    Если у :class:`ContextResult` есть атрибут ``structured_result``
    (итог работы :class:`paint_rag.knowledge.CompatibilityResolver` /
    :class:`paint_rag.knowledge.SystemResolver`), он вставляется в
    отдельный блок «STRUCTURED RESULT» ДО вопроса. LLM обязана
    опираться на этот блок в вопросах о совместимости и системах;
    переопределить его вывод она не может.
    
    Если у :class:`ContextResult` есть ``primary_recommendation``,
    она добавляется в блок «DETERMINISTIC RECOMMENDATION» — LLM
    обязана следовать этому выбору и не может его переопределить.
    """
    if result.has_context:
        context = result.context
    else:
        context = "В предоставленной документации информация не найдена."

    parts = [
        SYSTEM_INSTRUCTIONS,
        "",
        "CONTEXT:",
        context,
    ]

    # Add deterministic recommendation block if present
    if hasattr(result, "primary_recommendation") and result.primary_recommendation:
        parts.extend(["", _render_deterministic_recommendation(result)])

    structured = getattr(result, "structured_result", None)
    if structured:
        parts.extend(["", _render_structured_result(structured)])

    parts.extend(["", "QUESTION:", result.query])
    return "\n".join(parts)


# ----------------------------------------------------------------------
# Рендер структурированного результата совместимости/системы
# ----------------------------------------------------------------------


def _render_deterministic_recommendation(result: ContextResult) -> str:
    """Рендер блока DETERMINISTIC RECOMMENDATION, который LLM обязана соблюдать.
    
    Этот блок содержит результат детерминированного выбора primary system
    и alternatives, сделанный ContextBuilder на основе ranking engine.
    LLM НЕ может переопределить этот выбор.
    """
    lines = [
        "DETERMINISTIC RECOMMENDATION (выбор сделан ranking engine, LLM НЕ может изменить):"
    ]
    
    if result.primary_recommendation:
        primary = result.primary_recommendation
        lines.append("")
        lines.append("PRIMARY RECOMMENDATION (ОСНОВНАЯ РЕКОМЕНДАЦИЯ):")
        lines.append(f"  Система: {primary.system_name}")
        lines.append(f"  Ранг: {primary.rank}")
        lines.append(f"  Score: {primary.score:g}")
        if primary.application_scope:
            lines.append(f"  Область применения: {primary.application_scope}")
        if primary.ranking_factors:
            lines.append("  Факторы ранжирования:")
            for factor in primary.ranking_factors:
                lines.append(f"    - {factor}")
        lines.append("")
        lines.append("  ИНСТРУКЦИЯ: Ты ДОЛЖНА рекомендовать эту систему как основную.")
        lines.append("  Запрещено выбирать другую систему вместо PRIMARY RECOMMENDATION.")
    
    if result.alternatives:
        lines.append("")
        lines.append("ALTERNATIVES (альтернативы — справочная информация, не основные рекомендации):")
        for alt in result.alternatives:
            lines.append(f"  - Ранг {alt.rank}: {alt.system_name} (score: {alt.score:g})")
            if alt.application_scope:
                lines.append(f"    Область применения: {alt.application_scope}")
        lines.append("")
        lines.append("  ИНСТРУКЦИЯ: Ты можешь упомянуть альтернативы, но НЕ как основную рекомендацию.")
    
    lines.append("")
    lines.append(
        "ВЫВОД: LLM НЕ изменяет DETERMINISTIC RECOMMENDATION. "
        "При ответе используй PRIMARY RECOMMENDATION как основную систему, "
        "а alternatives только как справочную информацию."
    )
    return "\n".join(lines)


def _render_structured_result(structured: dict) -> str:
    """Текст блока STRUCTURED RESULT, который LLM обязана цитировать.

    ``structured`` — словарь:
      - ``status``: ``CONFIRMED`` / ``FORBIDDEN`` / ``UNKNOWN``;
      - ``relation``: строка описания (например, "primer_for");
      - ``reason``: причина (для FORBIDDEN/CONFIRMED);
      - ``conditions``: список условий (для CONFIRMED);
      - ``source``: словарь (file/sheet/page/row) — источник;
      - ``system``: (опц.) словарь по coating system;
      - ``notes``: пояснение почему статус именно такой.
    Если поля не заданы — блок рендерится с теми, что есть.
    """
    label = COMPATIBILITY_STATUS_LABELS.get(
        structured.get("status", "UNKNOWN"),
        structured.get("status", "UNKNOWN"),
    )
    lines = ["STRUCTURED RESULT (детерминированный вывод из базы знаний, не из LLM):"]
    lines.append(f"- Статус: {label}")
    if structured.get("relation"):
        lines.append(f"- Отношение: {structured['relation']}")
    if structured.get("reason"):
        lines.append(f"- Причина: {structured['reason']}")
    if structured.get("conditions"):
        lines.append(
            "- Условия: " + "; ".join(structured["conditions"])
        )
    if structured.get("note"):
        lines.append(f"- Примечание: {structured['note']}")
    src = structured.get("source") or {}
    if src:
        bits = [str(v) for k, v in src.items() if v is not None]
        if bits:
            lines.append("- Источник: " + ", ".join(bits))
    system = structured.get("system")
    if isinstance(system, dict):
        if system.get("name"):
            lines.append(f"- Система: {system['name']}")
        if system.get("layers"):
            lines.append(
                "- Слои системы: "
                + " → ".join(system["layers"])
            )
        if system.get("status"):
            lines.append(
                "- Статус системы: "
                + COMPATIBILITY_STATUS_LABELS.get(
                    system["status"], system["status"]
                )
            )
        if system.get("source"):
            bits = [str(v) for v in system["source"].values() if v is not None]
            if bits:
                lines.append("- Источник системы: " + ", ".join(bits))
    lines.append("")
    lines.append(
        "ВЫВОД: LLM НЕ изменяет статус выше. При CONFIRMED — "
        "рекомендуй продукт/систему и ссылайся на источник."
    )
    lines.append(
        "При FORBIDDEN — скажи, что комбинация ЗАПРЕЩЕНА, назови "
        "причину (из источника)."
    )
    lines.append(
        "При UNKNOWN — скажи, что в документации нет подтверждения "
        "совместимости/системы (НЕ «нельзя», НЕ «совместимо»)."
    )
    return "\n".join(lines)

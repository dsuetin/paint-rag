from __future__ import annotations

from pydantic import BaseModel, Field

from paint_rag.rag.context_result import ContextSource


class AnswerResult(BaseModel):
    """Итог работы AnswerGenerator (полный RAG-ответ).

    ``sources`` — нормализованные источники, пришедшие из retrieval
    context (НЕ выдуманные LLM). ``has_answer`` — False при отсутствии
    контекста (refusal), пустом ответе LLM, либо при ошибке LLM
    (см. ``refused`` и поведение с исключениями).

    Три раздельные ситуации:
    - NoContext         -> has_answer=False, refused=True, LLM не вызвана;
    - EmptyLLMResponse  -> has_answer=False, refusal_message;
    - LLMGenerationError -> бросается наружу (НЕ маскируется).
    """

    query: str
    answer: str
    sources: list[ContextSource] = Field(default_factory=list)
    has_answer: bool = False
    context_used: bool = False
    refusal: bool = False


def make_refusal(query: str) -> "AnswerResult":
    """Создать результат-отказ (нет достаточного контекста)."""
    return AnswerResult(
        query=query,
        answer=(
            "В базе знаний не найдено информации, достаточной "
            "для ответа на этот вопрос."
        ),
        sources=[],
        has_answer=False,
        context_used=False,
        refusal=True,
    )

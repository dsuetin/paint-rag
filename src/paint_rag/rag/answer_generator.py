from __future__ import annotations

from paint_rag.rag.answer_result import AnswerResult, make_refusal
from paint_rag.rag.context_builder import ContextBuilder
from paint_rag.rag.prompt_builder import build_prompt_from_result
from paint_rag.rag.llm import LLM, LLMGenerationError
from paint_rag.rag.strictness import check_strict_answer


class AnswerGenerator:
    """Объединяет ContextBuilder + PromptBuilder + LLM в один ответ.

    Pipeline:
        question
          -> ContextBuilder.build()   (внутри: Retriever -> VectorStore)
          -> PromptBuilder.build_prompt_from_result()
          -> LLM.generate()
          -> AnswerResult

    Ответы НЕ ищутся повторно. AnswerGenerator работает только
    через ContextBuilder и не обращается напрямую к Retriever /
    VectorStore / ProductStore.

    Отказ (refusal): если контекста нет (``has_context=False``),
    LLM НЕ вызывается — возвращается детерминированный отказ.
    Пустой ответ LLM тоже считается отказом. Исключения LLM не
    маскируются как отказ, а пробрасываются (обёрнутые в
    :class:`LLMGenerationError`).
    """

    def __init__(
        self,
        context_builder: ContextBuilder,
        llm: LLM,
        strict: bool = False,
    ) -> None:
        self.context_builder = context_builder
        self.llm = llm
        # Строгий режим отказа: детерминированная проверка ответа LLM
        # на признаки «додумывания» (отрицание + предположение).
        # Включается в production-pipeline и в evaluation-раннере.
        self.strict = strict

    def answer(
        self,
        query: str,
        top_k: int = 15,
        article: str | None = None,
        product: str | None = None,
        technology: str | None = None,
        max_chunks: int | None = None,
        max_chars: int | None = None,
        auto_detect_article: bool = True,
        use_hybrid: bool = True,
        semantic_weight: float = 1.0,
        lexical_weight: float = 1.5,
    ) -> AnswerResult:
        context_result = self.context_builder.build(
            query,
            top_k=top_k,
            article=article,
            product=product,
            technology=technology,
            max_chunks=max_chunks,
            max_chars=max_chars,
            auto_detect_article=auto_detect_article,
            use_hybrid=use_hybrid,
            semantic_weight=semantic_weight,
            lexical_weight=lexical_weight,
        )

        # Отказ: отсутствие контекста — LLM не вызывается.
        if not context_result.has_context:
            return make_refusal(query)

        prompt = build_prompt_from_result(context_result)

        answer_text = self._generate(prompt)

        # Пустой ответ LLM — это отказ, а не успешный ответ.
        if not answer_text or not answer_text.strip():
            return AnswerResult(
                query=query,
                answer=(
                    "В базе знаний информация найдена, однако "
                    "генерация ответа завершилась без результата."
                ),
                sources=context_result.sources,
                has_answer=False,
                context_used=True,
                refusal=True,
            )

        # Строгий режим: детерминированная проверка ответа на признаки
        # «додумывания поверх отказа» (отрицание + предположение).
        # При срабатывании — отвечаем честным отказом, а не
        # предположительным текстом с недоказанными фактами.
        if self.strict:
            check = check_strict_answer(answer_text)
            if check.is_hallucination:
                return _make_speculative_refusal(
                    query,
                    context_result,
                    check,
                )

        return AnswerResult(
            query=query,
            answer=answer_text,
            sources=context_result.sources,
            has_answer=True,
            context_used=True,
            refusal=False,
        )

    def _generate(self, prompt: str) -> str:
        try:
            return self.llm.generate(prompt)
        except LLMGenerationError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LLMGenerationError(
                f"LLM generation failed: {exc}"
            ) from exc


def _make_speculative_refusal(
    query: str,
    context_result,
    check,
) -> AnswerResult:
    """Честный отказ, когда LLM попыталась додумать поверх «не найдено».

    Источники (context) сохраняем — это действительно найденные данные;
    ``has_answer=False`` / ``refusal=True`` — потому что утвердительного
    подтверждённого ответа нет.
    """
    answer = (
        "В базе знаний не найдено подтверждения, достаточного для "
        "уверенного ответа на этот вопрос. Найдены лишь смежные "
        "данные, совместимость/применимость которых к заявленному "
        "вопросу документацией не подтверждена, поэтому конкретную "
        "рекомендацию давать нельзя."
    )
    return AnswerResult(
        query=query,
        answer=answer,
        sources=list(getattr(context_result, "sources", []) or []),
        has_answer=False,
        context_used=True,
        refusal=True,
    )

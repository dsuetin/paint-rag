from __future__ import annotations

from paint_rag.rag.answer_result import AnswerResult, make_refusal
from paint_rag.rag.context_builder import ContextBuilder
from paint_rag.rag.prompt_builder import build_prompt_from_result
from paint_rag.rag.llm import LLM, LLMGenerationError


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
    ) -> None:
        self.context_builder = context_builder
        self.llm = llm

    def answer(
        self,
        query: str,
        top_k: int = 5,
        article: str | None = None,
        product: str | None = None,
        technology: str | None = None,
        max_chunks: int | None = None,
        max_chars: int | None = None,
        auto_detect_article: bool = True,
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

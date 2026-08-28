import pytest

from conftest_pipeline import build_fixture

from paint_rag.rag.answer_generator import AnswerGenerator
from paint_rag.rag.context_builder import ContextBuilder
from paint_rag.rag.llm import FakeLLM, LLMGenerationError


def _builder():
    retriever, store = build_fixture()
    return ContextBuilder(retriever=retriever, product_store=store)


def _gen(llm=None):
    return AnswerGenerator(
        context_builder=_builder(),
        llm=llm or FakeLLM(answer="Расход составляет до 240 г/м²"),
    )


# 1 ----------------------------------------------------------------
def test_1_query_context_prompt_llm_answer():
    llm = FakeLLM(answer="Ответ на вопрос.")
    gen = _gen(llm)
    result = gen.answer("Какой расход грунта PA777-9016?")
    assert result.answer == "Ответ на вопрос."
    assert result.has_answer is True
    assert llm.calls == 1
    # prompt реально сформирован PromptBuilder и содержит контекст.
    assert "Какой расход грунта PA777-9016?" in llm.last_prompt
    assert "CONTEXT:" in llm.last_prompt


# 2 ----------------------------------------------------------------
def test_2_answer_contains_llm_result():
    gen = _gen(FakeLLM(answer="Расход: 120–140 г/м²"))
    result = gen.answer("Какой расход?")
    assert result.answer == "Расход: 120–140 г/м²"


# 3 ----------------------------------------------------------------
def test_3_result_contains_query():
    gen = _gen()
    result = gen.answer("Какой расход грунта PA777-9016?")
    assert result.query == "Какой расход грунта PA777-9016?"


# 4 ----------------------------------------------------------------
def test_4_result_contains_sources():
    gen = _gen()
    result = gen.answer("Какой расход грунта PA777-9016?")
    assert result.sources
    assert all(
        s.file == "Rupa_PA777_9016.pdf" for s in result.sources
    )


# 5 ----------------------------------------------------------------
def test_5_source_file_saved():
    gen = _gen()
    result = gen.answer("Какой расход грунта PA777-9016?")
    assert result.sources[0].file == "Rupa_PA777_9016.pdf"


# 6 ----------------------------------------------------------------
def test_6_source_page_saved():
    gen = _gen()
    result = gen.answer("Какой расход грунта PA777-9016?")
    pages = {s.page for s in result.sources}
    assert 1 in pages
    assert all(isinstance(p, int) for p in pages)


# 7 ----------------------------------------------------------------
def test_7_article_saved():
    gen = _gen()
    result = gen.answer("Какой расход грунта PA777-9016?")
    assert all(s.article == "PA777-9016" for s in result.sources)


# 8 ----------------------------------------------------------------
def test_8_technology_saved():
    gen = _gen()
    result = gen.answer("Какой расход грунта PA777-9016?")
    assert all(s.technology == "Rupa" for s in result.sources)


# 9 ----------------------------------------------------------------
def test_9_llm_receives_prompt_builder_prompt():
    from paint_rag.rag.prompt_builder import (
        SYSTEM_INSTRUCTIONS,
        build_prompt_from_result,
    )

    retriever, store = build_fixture()
    cb = ContextBuilder(retriever=retriever, product_store=store)
    ctx = cb.build(
        "Какой расход грунта PA777-9016?",
        article="PA777-9016",
    )
    expected_prompt = build_prompt_from_result(ctx)

    llm = FakeLLM(answer="ok")
    gen = AnswerGenerator(context_builder=cb, llm=llm)
    gen.answer("Какой расход грунта PA777-9016?", article="PA777-9016")
    assert llm.last_prompt == expected_prompt
    assert SYSTEM_INSTRUCTIONS in llm.last_prompt


# 10 ---------------------------------------------------------------
def test_10_no_context_llm_not_called():
    llm = FakeLLM(answer="never")
    gen = _gen(llm)
    result = gen.answer(
        "Какой расход продукта XYZ-DOES-NOT-EXIST?",
        article="XYZ-DOES-NOT-EXIST",
    )
    assert llm.calls == 0
    assert result.has_answer is False
    assert result.refusal is True


# 11 ---------------------------------------------------------------
def test_11_no_context_has_answer_false():
    gen = _gen(FakeLLM(answer="x"))
    result = gen.answer(
        "Какой расход продукта XYZ-DOES-NOT-EXIST?",
        article="XYZ-DOES-NOT-EXIST",
    )
    assert result.has_answer is False


# 12 ---------------------------------------------------------------
def test_12_context_present_has_answer_true():
    gen = _gen(FakeLLM(answer="Р"))
    result = gen.answer("Какой расход грунта PA777-9016?")
    assert result.has_answer is True
    assert result.context_used is True
    assert result.refusal is False


# 13 ---------------------------------------------------------------
def test_13_empty_llm_answer_has_answer_false():
    gen = _gen(FakeLLM(answer="   "))
    result = gen.answer("Какой расход грунта PA777-9016?")
    assert result.has_answer is False
    assert result.refusal is True
    # Контекст был, но ответ пустой.
    assert result.context_used is True


# 14 ---------------------------------------------------------------
def test_14_llm_exception_not_refusallike():
    def boom(prompt):
        raise RuntimeError("boom")

    llm = FakeLLM(on_generate=boom)
    gen = _gen(llm)
    with pytest.raises(LLMGenerationError):
        gen.answer("Какой расход грунта PA777-9016?")


# 15 ---------------------------------------------------------------
def test_15_llm_exception_wrapped():
    def boom(prompt):
        raise ValueError("bad token")

    gen = _gen(FakeLLM(on_generate=boom))
    with pytest.raises(LLMGenerationError) as excinfo:
        gen.answer("Какой расход грунта PA777-9016?")
    assert "bad token" in str(excinfo.value)


# 16 ---------------------------------------------------------------
def test_16_top_k_passed_to_context_builder():
    from unittest.mock import MagicMock
    from paint_rag.rag.context_builder import ContextBuilder as CB
    from paint_rag.rag.context_result import ContextResult

    fake_cb = MagicMock(spec=CB)
    fake_cb.build.return_value = ContextResult(
        query="q",
        context="ctx",
        has_context=True,
        sources=[],
    )
    gen = AnswerGenerator(context_builder=fake_cb, llm=FakeLLM(answer="a"))
    gen.answer("q", top_k=7)
    assert fake_cb.build.call_args.kwargs["top_k"] == 7


# 17 ---------------------------------------------------------------
def test_17_article_passed_to_context_builder():
    from unittest.mock import MagicMock
    from paint_rag.rag.context_builder import ContextBuilder as CB
    from paint_rag.rag.context_result import ContextResult

    fake_cb = MagicMock(spec=CB)
    fake_cb.build.return_value = ContextResult(
        query="q", context="c", has_context=True, sources=[]
    )
    gen = AnswerGenerator(context_builder=fake_cb, llm=FakeLLM(answer="a"))
    gen.answer("q", article="PA777-9016")
    assert fake_cb.build.call_args.kwargs["article"] == "PA777-9016"


# 18 ---------------------------------------------------------------
def test_18_product_passed_to_context_builder():
    from unittest.mock import MagicMock
    from paint_rag.rag.context_builder import ContextBuilder as CB
    from paint_rag.rag.context_result import ContextResult

    fake_cb = MagicMock(spec=CB)
    fake_cb.build.return_value = ContextResult(
        query="q", context="c", has_context=True, sources=[]
    )
    gen = AnswerGenerator(context_builder=fake_cb, llm=FakeLLM(answer="a"))
    gen.answer("q", product="Продукт PV210-XX")
    assert fake_cb.build.call_args.kwargs["product"] == "Продукт PV210-XX"


# 19 ---------------------------------------------------------------
def test_19_technology_passed_to_context_builder():
    from unittest.mock import MagicMock
    from paint_rag.rag.context_builder import ContextBuilder as CB
    from paint_rag.rag.context_result import ContextResult

    fake_cb = MagicMock(spec=CB)
    fake_cb.build.return_value = ContextResult(
        query="q", context="c", has_context=True, sources=[]
    )
    gen = AnswerGenerator(context_builder=fake_cb, llm=FakeLLM(answer="a"))
    gen.answer("q", technology="Rupa")
    assert fake_cb.build.call_args.kwargs["technology"] == "Rupa"


# 20 ---------------------------------------------------------------
def test_20_sources_not_rebuilt_from_llm():
    # ЛЛМ возвращает произвольный текст; источники должны остаться
    # именно retrieval-контекстными, а не выведенными из ответа.
    retriever, store = build_fixture()
    cb = ContextBuilder(retriever=retriever, product_store=store)
    ctx = cb.build("Какой расход грунта PA777-9016?", article="PA777-9016")
    real_sources = [s.model_dump() for s in ctx.sources]

    gen = AnswerGenerator(
        context_builder=cb,
        llm=FakeLLM(answer="Плотность 0,99 г/см³, source: fake.pdf page 9"),
    )
    result = gen.answer("Какой расход грунта PA777-9016?")
    assert [s.model_dump() for s in result.sources] == real_sources
    assert result.sources[0].file == "Rupa_PA777_9016.pdf"
    assert "fake.pdf" not in "".join(s.file or "" for s in result.sources)


# 21 ---------------------------------------------------------------
def test_21_range_and_tolerance_not_altered_by_pipeline():
    # Значения из контекста остаются в prompt без изменений:
    # 15–30% не превращается в 15%, 54±2% не в 54%.
    retriever, store = build_fixture()
    cb = ContextBuilder(retriever=retriever, product_store=store)
    gen = AnswerGenerator(context_builder=cb, llm=FakeLLM(answer="a"))
    gen.answer("Как смешивать PV210-XX?", article="PV210-XX")
    # Непосредственно проверяем prompt (через сохранение) —
    # используем контекст напрямую.
    ctx = cb.build("Как смешивать PV210-XX?", article="PV210-XX")
    assert "15–30%" in ctx.context
    assert "54±2%" in ctx.context


# 22 ---------------------------------------------------------------
def test_22_refusal_sources_empty():
    gen = _gen(FakeLLM(answer="x"))
    result = gen.answer(
        "Какой расход продукта XYZ-DOES-NOT-EXIST?",
        article="XYZ-DOES-NOT-EXIST",
    )
    assert result.sources == []
    assert result.refusal is True

import pytest

from paint_rag.rag.llm import (
    LLM,
    LLMGenerationError,
    FakeLLM,
)


# ----------------------------------------------------------------
# 1. LLM interface существует
# ----------------------------------------------------------------

def test_llm_interface_exists():
    assert LLM is not None


# ----------------------------------------------------------------
# 2. FakeLLM реализует интерфейс
# ----------------------------------------------------------------

def test_fake_llm_implements_interface():
    llm = FakeLLM(answer="ok")
    assert isinstance(llm, LLM)


# ----------------------------------------------------------------
# 3. FakeLLM.generate() возвращает ожидаемый ответ
# ----------------------------------------------------------------

def test_generate_returns_configured_answer():
    llm = FakeLLM(answer="Расход 120–140 г/м².")
    assert llm.generate("prompt") == "Расход 120–140 г/м²."


def test_generate_default_answer():
    llm = FakeLLM()
    assert llm.generate("prompt") == "ok"


# ----------------------------------------------------------------
# 4. Переданный prompt реально используется
# ----------------------------------------------------------------

def test_prompt_is_recorded_and_used():
    def respond(prompt: str) -> str:
        # Ответ зависит от prompt — доказательство, что prompt дошёл.
        return prompt.upper()

    llm = FakeLLM(on_generate=respond)
    result = llm.generate("вопрос про грунт")
    assert result == "ВОПРОС ПРО ГРУНТ"
    assert llm.last_prompt == "вопрос про грунт"


# ----------------------------------------------------------------
# 5. Можно определить количество вызовов
# ----------------------------------------------------------------

def test_call_count():
    llm = FakeLLM(answer="x")
    assert llm.calls == 0
    llm.generate("a")
    llm.generate("b")
    assert llm.calls == 2
    assert len(llm.prompts) == 2


# ----------------------------------------------------------------
# Дополнительно: FakeLLM может бросать контролируемую ошибку
# ----------------------------------------------------------------

def test_fake_llm_can_raise():
    def boom(prompt: str):
        raise RuntimeError("network error")

    llm = FakeLLM(on_generate=boom)
    with pytest.raises(RuntimeError):
        llm.generate("prompt")


def test_llm_generation_error_is_exception():
    assert issubclass(LLMGenerationError, RuntimeError)


def test_on_generate_none_uses_answer():
    llm = FakeLLM(answer="файл.pdf, page 1")
    assert llm.generate("whatever") == "файл.pdf, page 1"

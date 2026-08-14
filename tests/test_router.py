from paint_rag.router import (
    QuestionType,
    classify_question,
)


def test_calculation_question():

    assert (
        classify_question(
            "Сколько PA334-9016 нужно на 50 м2?"
        )
        == QuestionType.CALCULATION
    )


def test_mixing_question():

    assert (
        classify_question(
            "Как смешивать PA334-9016?"
        )
        == QuestionType.MIXING
    )


def test_compatibility_question():

    assert (
        classify_question(
            "Можно ли наносить PU на WB?"
        )
        == QuestionType.COMPATIBILITY
    )
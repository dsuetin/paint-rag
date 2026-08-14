from enum import Enum


class QuestionType(str, Enum):
    PRODUCT = "product"
    MIXING = "mixing"
    COMPATIBILITY = "compatibility"
    CALCULATION = "calculation"
    DOCUMENTATION = "documentation"


def classify_question(
    question: str,
) -> QuestionType:

    q = question.lower()

    if any(
        word in q
        for word in [
            "сколько",
            "расход",
            "м²",
            "м2",
            "площад",
        ]
    ):
        return QuestionType.CALCULATION

    if any(
        word in q
        for word in [
            "смеш",
            "отверд",
            "разбав",
            "пропорц",
        ]
    ):
        return QuestionType.MIXING

    if any(
        word in q
        for word in [
            "можно ли",
            "наносить на",
            "совместим",
        ]
    ):
        return QuestionType.COMPATIBILITY

    return QuestionType.PRODUCT
"""Product-level compatibility relations (TЗ §2, §5, §7).

Отличаются от :class:`paint_rag.models.compatibility.CompatibilityRule`:

- ``base`` / ``top`` — это **артикулы** продуктов (``PD155``, ``SC-T470`` …),
  а не химические системы (``PU``, ``WB``).
- ``allowed`` имеет явный статус ``CONFIRMED`` / ``FORBIDDEN``.
- **``source`` обязателен** (file / page / sheet / row / note) —
  без источника правило не существует.

Отсутствие правила ≠ запрещённая комбинация: для отсутствующих пар
:class:`paint_rag.knowledge.compatibility_resolver.CompatibilityResolver`
вернёт ``UNKNOWN``.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class RelationSource(BaseModel):
    """Исходник правила. Обязателен."""
    file: str | None = None
    page: int | None = None
    sheet: str | None = None
    row: int | None = None
    product: str | None = None
    note: str | None = None

    def as_dict(self) -> dict:
        d = {
            "file": self.file,
            "page": self.page,
            "sheet": self.sheet,
            "row": self.row,
            "product": self.product,
            "note": self.note,
        }
        return {k: v for k, v in d.items() if v is not None}

    @property
    def has_provenance(self) -> bool:
        return bool(self.file or self.sheet or self.row or self.note)


class RelationAlternative(BaseModel):
    """Альтернатива («или») внутри одной связи/рецептуры.

    Это НЕ coating compatibility: «Подходящий Праймер: Д-дур грунт, УС грунт»
    → УС грунт — альтернатива праймера, а не отдельная связка.
    """
    ref: str                 # код/название альтернативы (``7000-012009``, ``УС грунт``)
    role: str | None = None  # primer / hardener / thinner / finish
    note: str | None = None  # цитата из TDS


class ProductRelation(BaseModel):
    """Связь «top-продукт» → «base-продукт» (base под top).

    Например, D-DUR: base=«Д-дур грунт 1149», top=«Д-дур 01 эмаль
    2675-755251», allowed=True — из «Эмаль Д-Дур база 01 полумат.pdf»,
    строчка «Подлежащий Праймер: Д-дур грунт».

    ``level`` — уровень подтверждения (из docs/confirmed_product_relations.md):
    ART = конкретный артикул; VAR = конкретный вариант; PROD = только
    семейство/серия (без артикула). ART/VAR-связи НЕ поднимаются до PROD
    и НЕ распространяются автоматически на другие варианты.
    """
    base: str            # код base (артикул/семейный код продукта под top)
    top: str             # код top (артикул/семейный код продукта над base)
    allowed: bool
    status: str = "CONFIRMED"  # CONFIRMED | FORBIDDEN
    level: str = "ART"         # ART | VAR | PROD
    base_product: str | None = None  # человекочитаемое имя base (опц.)
    top_product: str | None = None   # человекочитаемое имя top (опц.)
    reason: str | None = None
    conditions: list[str] = Field(default_factory=list)
    alternatives: list[RelationAlternative] = Field(
        default_factory=list
    )
    source: RelationSource = Field(default_factory=RelationSource)

    @property
    def is_confirmed(self) -> bool:
        return self.status == "CONFIRMED" and self.allowed

    @property
    def is_forbidden(self) -> bool:
        return self.status == "FORBIDDEN" and not self.allowed


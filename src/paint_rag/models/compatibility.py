from pydantic import BaseModel, Field, model_validator


class CompatibilitySource(BaseModel):
    """Источник правила совместимости (provenance).

    Обязательны для новых правил; для legacy правил (compatibility.json
    2024 без source) допускают отсутствующие поля — статус при этом
    считается «подтверждённым» (allow), но «без трассируемого источника»
    и в ответах помечается как ``legacy``.
    """
    file: str | None = None
    page: int | None = None
    sheet: str | None = None
    row: int | None = None
    product: str | None = None
    note: str | None = None


class CompatibilityRule(BaseModel):
    """Структурная связь совместимости между нижним (base) и верхним
    (top) слоями.

    ``base``/``top`` могут быть:
      * хим. системой (NC / AC / PU / PE / UV / WB) — из
        ``data/knowledge/compatibility.json`` (legacy, без page);
      * артикулом продукта (``PD155``, ``SC-T470`` …) — из
        продуктов/ТД (source с file + page).

    Статус:
      - ``CONFIRMED`` — база подтверждает связь (``allowed=True``);
      - ``FORBIDDEN`` — база запрещает (``allowed=False``);
      - ``UNKNOWN``    — база НЕ содержит правила; устанавливается
        :class:`paint_rag.knowledge.CompatibilityResolver`, а не хранится
        в store (отсутствие ≠ запрет).
    """
    base: str
    top: str

    allowed: bool

    reason: str | None = None
    conditions: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)

    # Провенанс правила. Для legacy compatibility.json может быть пусто.
    source: CompatibilitySource = Field(
        default_factory=CompatibilitySource
    )

    @property
    def status(self) -> str:
        """``CONFIRMED`` / ``FORBIDDEN`` (legacy → оба с ``allowed``).

        Отдельный статус ``UNKNOWN`` не хранится в этом правиле —
        его возвращает :class:`CompatibilityResolver` для отсутствующих
        пар.
        """
        return "CONFIRMED" if self.allowed else "FORBIDDEN"

    @model_validator(mode="after")
    def _normalize_base_top(self):
        # Приводим в верхний регистр, чтобы store.find("wb","pu") и
        # find("WB","PU") находили одно и то же правило (как раньше,
        # только теперь и в модели).
        self.base = self.base.upper()
        self.top = self.top.upper()
        return self
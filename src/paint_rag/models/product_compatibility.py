"""Модели совместимости на уровне продуктов и систем покрытия.

Разделены от :mod:`paint_rag.models.compatibility`, потому что
«системы нанесения» (Таблица1/2/3 Excel «Системы нанесения») — это
связи между несколькими продуктами по подложке, а не просто
base↔top. Здесь держим:

- :class:`ProductRole`           — «что это за продукт» (грунт/лак/эмаль/
                                    изолятор/антисептик…);
- :class:`ProductSubstrate`      — подложки (wood_solid/veneer/MDF/MDF_veneered/
                                    parquet/terrace/window…);
- :class:`CoatingSystem`         — именованная система покрытия (T1/T2/T3
                                    «Системы нанесения» Excel +
                                    «Примеры систем под кисть» PDF Holzhaus);
- :class:`SystemLayer`           — роль слоя в системе (primer / isolator /
                                    intermediate / topcoat / antisepicant).

Все эти модели имеют ``source`` (file/sheet/row/page/product) — трассируемость
обязательна. Отсутствие источника НЕ создаёт связи.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


# ----------------------------------------------------------------------
# Product-level metadata (role, substrates)
# ----------------------------------------------------------------------


class ProductRoleSource(BaseModel):
    """Источник роли/подложки в документации."""
    file: str | None = None
    page: int | None = None
    sheet: str | None = None
    row: int | None = None
    note: str | None = None


class RoleSubstrate(BaseModel):
    """Подложка (substrate), на которую продукт применяется по документации.

    ``substrate`` — нормализованное имя (``mdf``, ``wood_solid``, ``veneer``,
    ``parquet``, ``terrace``, ``window``, ``outdoor``, ``indoor``, ``plastic``,
    ``metal``, ``child_furniture`` …). ``note`` — цитата из документации с
    обоснованием (например, «МДФ (изолятор)» из ``usage`` PD155).
    """
    substrate: str
    note: str | None = None
    source: ProductRoleSource = Field(
        default_factory=ProductRoleSource
    )


class ProductRole(BaseModel):
    """Роль продукта + допустимые подложки (по документации).

    ``role`` — одна из: ``primer``, ``isolator``, ``filler``, ``primer_isolator``,
    ``topcoat``, ``finish`` (лак/эмаль), ``antiseptic``, ``stain``,
    ``intermediate``, ``multi_role`` (3в1)… Точное значение — из ``usage``.

    Эти данные НЕ «додуманы»: ``role`` / ``substrates`` заполняются из
    текстов ``usage`` / ``technical_data`` в PDF (например,
    PD155: «барьерный грунт на МДФ»).
    """
    role: str | None = None
    substrates: list[RoleSubstrate] = Field(default_factory=list)
    source: ProductRoleSource = Field(
        default_factory=ProductRoleSource
    )


# ----------------------------------------------------------------------
# Coating system (T1–T3 «Системы нанесения» Excel + PDF)
# ----------------------------------------------------------------------


class SystemLayer(BaseModel):
    """Один слой в coating system.

    ``role`` — ``primer`` / ``isolator`` / ``filler`` / ``intermediate`` /
    ``topcoat`` / ``antiseptic`` / ``finish``;
    ``product`` — название продукта из ТД Excel (``Грунт Трэфф Тэксурф``)
    и/или артикул из products.json (``PD155``), если сопоставимы.
    ``article`` — артикул (если найден в products.json).
    """
    role: str
    name: str | None = None       # из ТД Excel (название продукта в системе)
    article: str | None = None    # артикул (если сопоставим)
    layers_count: int | None = None  # «3x» в системе (Holzhaus PDF)


class CoatingSystem(BaseModel):
    """Именованная система покрытия (по ТД «Системы нанесения» Excel и PDF).

    ``substrates`` — подложки, где система допустима (Т3: + в колонке);
    пустой список = система НЕ разрешена для этой подложки (T2/T3 «Тип
    изделий» + матрица).

    ``status`` — ``CONFIRMED`` (система описана документацией, имеет
    provenance). Отсутствие системы для подложки ≠ FORBIDDEN — для неё
    :class:`paint_rag.knowledge.SystemResolver` вернёт ``UNKNOWN``.
    """
    name: str
    materials_text: str | None = None      # «Материалы, входящие в систему» (T1)
    layers: list[SystemLayer] = Field(default_factory=list)
    # substrates — machine-ключи (door_furniture_mdf …) — из T3 (плюс = True)
    substrates: list[str] = Field(default_factory=list)
    # substrate_labels — человекочитаемые подписи подложек (опц., из Excel
    # «Типы изделий» / заголовков Т3). Хранится для ответа, не для поиска.
    substrate_labels: list[str] = Field(default_factory=list)
    # item_types_text — «Типы изделий» (T2) как есть.
    item_types: str | None = None
    # application_scope — INTERIOR/EXTERIOR/BOTH/UNKNOWN, derived from item_types
    application_scope: str | None = None
    advantages: str | None = None          # «Достоинства» (T2)
    disadvantages: str | None = None       # «Недостатки» (T2)
    status: str = "CONFIRMED"
    source: ProductRoleSource = Field(default_factory=ProductRoleSource)

from typing import Optional
from enum import Enum

from pydantic import BaseModel, Field
import re

from paint_rag.models.product_compatibility import ProductRole
from paint_rag.models.product_relation import (
    ProductRelation,
    RelationAlternative,
    RelationSource,
)
from paint_rag.models.chemical_system import (
    ChemicalSystem,
    UNKNOWN as _CHEM_UNKNOWN,
)


class ApplicationScope(str, Enum):
    """Область применения продукта."""
    INTERIOR = "INTERIOR"
    EXTERIOR = "EXTERIOR"
    BOTH = "BOTH"
    UNKNOWN = "UNKNOWN"


class ApplicationRoleSource(BaseModel):
    """Роль продукта с источником."""
    role: str
    source_file: Optional[str] = None
    source_section: Optional[str] = None


class DictMixin:
    """Index access на pydantic-модель как на словарь: model['field']."""

    def __getitem__(self, key: str):
        if key not in type(self).model_fields:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key: str, default=None):
        if key not in type(self).model_fields:
            return default
        return getattr(self, key)


class Ratio(DictMixin, BaseModel):
    min: float
    max: float


class MixingComponent(BaseModel):
    name: Optional[str] = None
    percent: Optional[float] = None
    percent_min: Optional[float] = None
    percent_max: Optional[float] = None


class MixingRule(BaseModel):
    base_percent: float = 100.0

    hardener: Optional[MixingComponent] = None
    thinner: Optional[MixingComponent] = None

    total_ratio: Optional[float] = None
    raw: Optional[str] = None

    @property
    def hardener_name(self) -> Optional[str]:
        if self.hardener is None:
            return None

        return self.hardener.name

    @property
    def thinner_name(self) -> Optional[str]:
        if self.thinner is None:
            return None

        return self.thinner.name


    @property
    def hardener_ratio(self) -> Optional[Ratio]:
        if self.hardener is None:
            return None

        minimum = (
            self.hardener.percent_min
            if self.hardener.percent_min is not None
            else self.hardener.percent
        )

        maximum = (
            self.hardener.percent_max
            if self.hardener.percent_max is not None
            else self.hardener.percent
        )

        return Ratio(
            min=minimum,
            max=maximum,
        )

    @property
    def thinner_ratio(self) -> Ratio | None:
        if self.thinner is None:
            return None

        if (
            self.thinner.percent_min is not None
            and self.thinner.percent_max is not None
        ):
            return Ratio(
                min=self.thinner.percent_min,
                max=self.thinner.percent_max,
            )

        # Fallback для старого JSON / старого parser-а.
        if self.raw:
            match = re.search(
                r"Разбав(?:итель|ителя|ителем)?\s*"
                r"(\d+(?:[.,]\d+)?)\s*[-–—]\s*"
                r"(\d+(?:[.,]\d+)?)\s*%",
                self.raw,
                re.IGNORECASE,
            )

            if match:
                return Ratio(
                    min=float(match.group(1).replace(",", ".")),
                    max=float(match.group(2).replace(",", ".")),
                )

        if self.thinner.percent is not None:
            return Ratio(
                min=self.thinner.percent,
                max=self.thinner.percent,
            )

        return None


class Coverage(BaseModel):
    value: float
    unit: str


class Component(BaseModel):
    article: Optional[str] = None
    name: Optional[str] = None


class CalculationComponent(BaseModel):
    kg: Optional[float] = None
    cost: Optional[float] = None


class CalculationTotal(BaseModel):
    cost: Optional[float] = None


class CalculationReference(BaseModel):
    base: Optional[CalculationComponent] = None
    hardener: Optional[CalculationComponent] = None
    thinner: Optional[CalculationComponent] = None
    total: Optional[CalculationTotal] = None

    # Оставляем для совместимости со старым JSON
    total_cost: Optional[float] = None


class VariantSource(BaseModel):
    sheet: str
    product_row: int

    price_column: Optional[int] = None
    calculation_column: Optional[int] = None
    cost_column: Optional[int] = None

    base_row: Optional[int] = None
    hardener_row: Optional[int] = None
    thinner_row: Optional[int] = None
    total_row: Optional[int] = None


class ProductSource(DictMixin, BaseModel):
    sheet: Optional[str] = None
    row: Optional[int] = None

    file: Optional[str] = None
    page: Optional[int] = None

class ProductVariant(BaseModel):
    variant_id: int

    article: Optional[str] = None

    price: Optional[float] = None

    coverage: Optional[Coverage] = None

    mixing: Optional[MixingRule] = None

    components: dict[str, Optional[Component]] = Field(
        default_factory=dict
    )

    calculation_reference: Optional[
        CalculationReference
    ] = None

    # Variant-level совместимые связи (напр., «PA777-9016 → HD816»
    # относится ТОЛЬКО к этому варианту). Эффективная совместимость
    # варианта = product.compatibility + variant.compatibility
    # (вариантный уровень приоритетнее; нет авто-наследования в обе
    # стороны — ТЗ этап 5).
    compatibility: list[ProductRelation] = Field(
        default_factory=list
    )

    # Альтернативы компонентов рецептуры («или»):
    # напр. PA777-9016: HD816 основной, HD865 — альтернативный
    # отвердитель. НЕ coating compatibility (см. §4 confirmed relations).
    alternatives: list[RelationAlternative] = Field(
        default_factory=list
    )

    # Источники variant-level данных (PDF file/page, Excel sheet/row).
    sources: list[RelationSource] = Field(
        default_factory=list
    )

    source: VariantSource

    @property
    def unit_price(self) -> Optional[float]:
        return self.price


class ApplicationLayer(BaseModel):
    """Один слой в последовательности нанесения.
    
    role: роль слоя (primer/isolator/topcoat/intermediate/antiseptic)
    product_name: название продукта для этого слоя
    article: артикул продукта
    layers_count: количество слоёв этого типа (например, "2-3")
    notes: примечания (например, "с межслойной шлифовкой")
    """
    role: str
    product_name: Optional[str] = None
    article: Optional[str] = None
    layers_count: Optional[str] = None
    notes: Optional[str] = None


class TechnicalData(BaseModel):
    # Значения сохраняются строками, чтобы без потерь
    # держать диапазоны ("15–30%"), допуски ("54±2%")
    # и текстовые значения ("до 12 часов").
    gloss: Optional[str] = None
    dry_residue: Optional[str] = None
    density: Optional[str] = None
    viscosity: Optional[str] = None
    pot_life: Optional[str] = None
    drying: Optional[str] = None
    shelf_life: Optional[str] = None
    application: Optional[str] = None
    description: Optional[str] = None
    usage: Optional[str] = None


class Product(BaseModel):
    name: str

    article: Optional[str] = None

    technology: Optional[str] = None

    aliases: list[str] = Field(
        default_factory=list
    )

    consumption_min: Optional[float] = None
    consumption_max: Optional[float] = None
    consumption_unit: Optional[str] = None

    max_layers: Optional[int] = None

    variants: list[ProductVariant] = Field(
        default_factory=list
    )

    mixing: Optional[MixingRule] = None

    technical_data: Optional[TechnicalData] = None

    # Роль продукта (primer / isolator / topcoat …) + допустимые подложки.
    # Заполняется только при наличии подтверждения в документации (usage /
    # technical_data / ТД «Системы нанесения»). Для продуктов без данных — null.
    role: Optional[ProductRole] = None

    # Совместимость «top-продукт над этим продуктом»: только явные
    # CONFIRMED/FORBIDDEN связи с первичным источником (каждая
    # ProductRelation несёт base, top, status, reason, conditions,
    # source). Пустой список = UNKNOWN (отсутствие связи ≠ запрет).
    # Заполняется только из подтверждённых первичных источников;
    # по хим. классу НЕ выводится (ТЗ §8).
    # Смешивание (hardener/thinner) и coating systems здесь НЕ хранятся.
    compatibility: list[ProductRelation] = Field(
        default_factory=list
    )

    # Альтернативы компонентов рецептуры продукта («или»:
    # основной отвердитель HD816 / альтернативный HD865 и т.п., §4
    # confirmed relations). НЕ coating compatibility.
    alternatives: list[RelationAlternative] = Field(
        default_factory=list
    )

    # Источники product-level данных (PDF file/page или Excel sheet/row).
    # Отдельные строки данных (рецептуры, альтернативы, совместимость),
    # не вошедшие в variant.source.
    sources: list[RelationSource] = Field(
        default_factory=list
    )

    # Химическая система (NC/AC/PU/PE/UV/WB) — только при явном
    # подтверждении в первичном TDS. UNKNOWN = нет подтверждения.
    # Не выводится из названия, роли, папки или сходства.
    chemical_system: Optional[ChemicalSystem] = None

    # Последовательность нанесения слоёв (из PDF или coating systems)
    # Указывает порядок: какой слой первый, какой второй и т.д.
    application_order: Optional[list[ApplicationLayer]] = None

    # Все документированные роли продукта (один продукт может иметь несколько ролей)
    # Например: ['primer', 'isolator', 'topcoat']
    # Каждая роль должна иметь подтверждение в документации
    application_roles: Optional[list[str]] = None

    # Область применения: INTERIOR/EXTERIOR/BOTH/UNKNOWN
    # Определяется из документации (description, usage, название)
    application_scope: Optional[ApplicationScope] = None

    # Источник информации об области применения
    application_scope_source: Optional[str] = None

    source: Optional[ProductSource] = None

    def effective_compatibility(
        self,
        variant=None,
    ) -> list[ProductRelation]:
        """Effective-совместимость = product-level + variant-level.

        Вариантный уровень — более специфичный — проверяется первым;
        авто-наследования в обе стороны нет (ТЗ этап 5). Отсутствие
        любой связи = UNKNOWN, а не FORBIDDEN.
        """
        out: list[ProductRelation] = []
        if variant is not None:
            out.extend(list(getattr(variant, "compatibility", None) or []))
        out.extend(list(self.compatibility or []))
        return out
from typing import Optional

from pydantic import BaseModel, Field


class Ratio(BaseModel):
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


class ProductSource(BaseModel):
    sheet: str
    row: int

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

    source: VariantSource

    @property
    def unit_price(self) -> Optional[float]:
        return self.price


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

    source: Optional[ProductSource] = None
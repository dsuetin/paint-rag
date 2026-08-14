from typing import Optional

from pydantic import BaseModel, Field
import re

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
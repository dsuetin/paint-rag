from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def is_nan(value: Any) -> bool:
    return pd.isna(value)


def clean(value: Any) -> str | None:
    if value is None or is_nan(value):
        return None

    value = str(value).strip()

    if not value or value.lower() == "nan":
        return None

    return value


def to_float(value: Any) -> float | None:
    if value is None or is_nan(value):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return None


def is_number(value: Any) -> bool:
    return to_float(value) is not None


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )


# ---------------------------------------------------------
# Mixing parser
# ---------------------------------------------------------

MIXING_RE = re.compile(
    r"""
    100\s*%
    \s*\+\s*
    (?P<hardener>\d+(?:[.,]\d+)?)\s*%
    \s*
    \((?P<hardener_name>[^)]+)\)
    \s*\+\s*
    (?P<thinner_min>\d+(?:[.,]\d+)?)
    \s*(?:[-–—]\s*(?P<thinner_max>\d+(?:[.,]\d+)?))?\s*%
    """,
    re.VERBOSE | re.IGNORECASE,
)


def parse_mixing(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None

    # Нормализуем тире
    normalized = (
        text
        .replace("—", "-")
        .replace("–", "-")
        .replace("−", "-")
    )

    # Например:
    # PA334-9016 100%; HD816 33%; Разбавитель 15-30%

    parts = [
        part.strip()
        for part in normalized.split(";")
        if part.strip()
    ]

    if len(parts) < 2:
        return None

    base_percent = 100.0
    hardener = None
    thinner = None

    for part in parts:

        # 100%
        base_match = re.search(
            r"(\d+(?:[.,]\d+)?)\s*%",
            part,
        )

        if not base_match:
            continue

        percent = float(
            base_match.group(1).replace(",", ".")
        )

        lower = part.lower()

        # Отвердитель
        if (
            "отверд" in lower
            or "hardener" in lower
            or "hd" in lower
        ):
            name = part[:base_match.start()].strip()

            hardener = {
                "name": name,
                "percent": percent,
            }

        # Разбавитель
        elif (
            "разбав" in lower
            or "разбов" in lower
            or "thinner" in lower
        ):
            range_match = re.search(
                r"(\d+(?:[.,]\d+)?)\s*-\s*(\d+(?:[.,]\d+)?)\s*%",
                part,
            )

            if range_match:
                thinner_min = float(
                    range_match.group(1).replace(",", ".")
                )
                thinner_max = float(
                    range_match.group(2).replace(",", ".")
                )
            else:
                thinner_min = percent
                thinner_max = percent

            thinner = {
                "name": "Разбавитель",
                "percent": thinner_min,
                "percent_min": thinner_min,
                "percent_max": thinner_max,
            }

    if hardener is None and thinner is None:
        return None

    return {
        "base_percent": base_percent,
        "hardener": hardener,
        "thinner": thinner,
        "total_ratio": None,
        "raw": text,
    }
# ---------------------------------------------------------
# Product block detection
# ---------------------------------------------------------

def looks_like_product_name(value: Any) -> bool:
    value = clean(value)

    if not value:
        return False

    if value.startswith("Расход"):
        return False

    if value in {
        "S м2 =",
        "Цена:",
        "Итого:",
    }:
        return False

    if value.startswith("м2 на"):
        return False

    if "←" in value:
        return False

    return True


def is_product_row(df: pd.DataFrame, row: int) -> bool:
    first = clean(df.iloc[row, 0])

    if not looks_like_product_name(first):
        return False

    # Следующая строка обычно содержит "м2 на 1кг".
    if row + 1 < len(df):
        second = clean(df.iloc[row + 1, 1])

        if second and "м2" in second.lower():
            return True

    # Иногда структура листа может отличаться.
    # Если в строке есть "Смесь =", тоже считаем её продуктом.
    for col in range(min(5, df.shape[1])):
        value = clean(df.iloc[row, col])

        if value and "смесь =" in value.lower():
            return True

    return False


# ---------------------------------------------------------
# Variant columns
# ---------------------------------------------------------

def detect_variant_columns(
    df: pd.DataFrame,
    product_row: int,
) -> list[int]:

    """
    В Excel один вариант занимает две колонки:

        quantity | cost
        ---------+-----
        0.09259  | 46.11

    В верхней строке находится цена базового материала:

        ... | 155 | ... | 125 | ... | 118

    Поэтому вариантами являются колонки с ценой:
        2, 4, 6, ...

    """
    columns: list[int] = []

    for col in range(2, df.shape[1]):

        value = to_float(
            df.iloc[product_row, col]
        )

        if value is None:
            continue

        # Проверяем, что рядом действительно
        # есть расчётная колонка.
        if col + 1 < df.shape[1]:

            columns.append(col)

    return columns


# ---------------------------------------------------------
# Calculation rows
# ---------------------------------------------------------

def find_row(
    df: pd.DataFrame,
    start: int,
    max_rows: int,
    text: str,
) -> int | None:

    end = min(
        start + max_rows,
        len(df),
    )

    text = text.lower()

    for row in range(start, end):

        for col in range(df.shape[1]):

            value = clean(df.iloc[row, col])

            if value and text in value.lower():
                return row

    return None


def find_next_product(
    df: pd.DataFrame,
    start: int,
) -> int | None:

    for row in range(start, len(df)):

        if is_product_row(df, row):
            return row

    return None


# ---------------------------------------------------------
# Component extraction
# ---------------------------------------------------------

def parse_component_row(
    df: pd.DataFrame,
    row: int | None,
) -> dict[str, Any] | None:

    if row is None:
        return None

    article = clean(df.iloc[row, 0])

    name = clean(df.iloc[row, 1])

    if not name:
        return None

    return {
        "article": article,
        "name": name,
    }

def get_cell(
    df: pd.DataFrame,
    row: int | None,
    col: int,
) -> float | None:

    if row is None:
        return None

    if row >= len(df):
        return None

    if col >= df.shape[1]:
        return None

    return to_float(
        df.iloc[row, col]
    )


def parse_calculation(
    df: pd.DataFrame,
    variant_col: int,
    base_row: int | None,
    hardener_row: int | None,
    thinner_row: int | None,
    total_row: int | None,
) -> dict[str, Any]:

    base_kg = get_cell(
        df,
        base_row,
        variant_col,
    )

    hardener_kg = get_cell(
        df,
        hardener_row,
        variant_col,
    )

    thinner_kg = get_cell(
        df,
        thinner_row,
        variant_col,
    )

    # В соседней колонке находится стоимость.
    cost_col = variant_col + 1

    base_cost = get_cell(
        df,
        base_row,
        cost_col,
    )

    hardener_cost = get_cell(
        df,
        hardener_row,
        cost_col,
    )

    thinner_cost = get_cell(
        df,
        thinner_row,
        cost_col,
    )

    total_cost = get_cell(
        df,
        total_row,
        variant_col,
    )

    # В некоторых версиях Excel итог может
    # находиться в соседней колонке.
    if total_cost is None:
        total_cost = get_cell(
            df,
            total_row,
            cost_col,
        )

    return {
        "base": {
            "kg": base_kg,
            "cost": base_cost,
        },

        "hardener": {
            "kg": hardener_kg,
            "cost": hardener_cost,
        },

        "thinner": {
            "kg": thinner_kg,
            "cost": thinner_cost,
        },

        "total": {
            "cost": total_cost,
        },
    }

# ---------------------------------------------------------
# Product block
# ---------------------------------------------------------

def parse_product_block(
    df: pd.DataFrame,
    product_row: int,
    next_product_row: int | None,
    sheet_name: str,
) -> dict[str, Any]:

    product_name = clean(
        df.iloc[product_row, 0]
    )

    mixing_texts: list[str] = []

    for col in range(
        1,
        df.shape[1],
    ):
        value = clean(
            df.iloc[product_row, col]
        )

        if value and "смесь =" in value.lower():
            mixing_texts.append(value)

    variant_columns = detect_variant_columns(
        df,
        product_row,
    )

    coverage_row = None

    if product_row + 1 < len(df):
        value = clean(
            df.iloc[product_row + 1, 1]
        )

        if value and "м2 на" in value.lower():
            coverage_row = product_row + 1

    # Ограничиваем поиск расчётных строк текущим блоком.
    block_end = (
        next_product_row
        if next_product_row is not None
        else len(df)
    )

    block_df = df.iloc[
        product_row:block_end
    ]

    hardener_row = None
    thinner_row = None
    base_row = None
    total_row = None

    for local_row in range(len(block_df)):

        absolute_row = (
            product_row + local_row
        )

        for col in range(
            block_df.shape[1]
        ):

            value = clean(
                block_df.iloc[
                    local_row,
                    col,
                ]
            )

            if not value:
                continue

            lower = value.lower()

            if (
                "расход грунта" in lower
                or "расход лака" in lower
                or "расход краски" in lower
            ):
                base_row = absolute_row

            elif "расход отвердителя" in lower:
                hardener_row = absolute_row

            elif (
                "расход разбовителя" in lower
                or "расход разбавителя" in lower
            ):
                thinner_row = absolute_row

            elif "итого:" in lower:
                total_row = absolute_row

    variants: list[dict[str, Any]] = []

    for index, col in enumerate(variant_columns):

        price = to_float(
            df.iloc[
                product_row,
                col,
            ]
        )

        coverage = None

        if coverage_row is not None:
            coverage = to_float(
                df.iloc[
                    coverage_row,
                    col,
                ]
            )

        mixing_text = (
            mixing_texts[index]
            if index < len(mixing_texts)
            else None
        )

        mixing = parse_mixing(
            mixing_text
        )

        base_component = (
            parse_component_row(
                df,
                base_row,
            )
            if base_row is not None
            else None
        )

        hardener_component = (
            parse_component_row(
                df,
                hardener_row,
            )
            if hardener_row is not None
            else None
        )

        thinner_component = (
            parse_component_row(
                df,
                thinner_row,
            )
            if thinner_row is not None
            else None
        )

        calculation = parse_calculation(
            df=df,
            variant_col=col,
            base_row=base_row,
            hardener_row=hardener_row,
            thinner_row=thinner_row,
            total_row=total_row,
        )

        # Итого может быть в той же колонке.
        if total_row is not None:
            calculation["total_cost"] = to_float(
                df.iloc[
                    total_row,
                    col,
                ]
            )

        variant = {
            "variant_id": index + 1,

            "price": price,

            "coverage": {
                "value": coverage,
                "unit": "m2_per_kg",
            },

            "mixing": mixing,

            "components": {
                "base": base_component,
                "hardener": hardener_component,
                "thinner": thinner_component,
            },

            "calculation_reference": calculation,

            "source": {
                "sheet": sheet_name,
                "product_row": product_row + 1,
                "price_column": col,
                "calculation_column": col,
                "cost_column": col + 1,
                "base_row": (
                    base_row + 1
                    if base_row is not None
                    else None
                ),
                "hardener_row": (
                    hardener_row + 1
                    if hardener_row is not None
                    else None
                ),
                "thinner_row": (
                    thinner_row + 1
                    if thinner_row is not None
                    else None
                ),
                "total_row": (
                    total_row + 1
                    if total_row is not None
                    else None
                ),
            },
        }

        variants.append(variant)

    return {
        "name": product_name,

        "technology": sheet_name,

        "aliases": [],

        "variants": variants,

        "source": {
            "sheet": sheet_name,
            "row": product_row + 1,
        },
    }


# ---------------------------------------------------------
# Sheet parser
# ---------------------------------------------------------

def parse_sheet(
    path: Path,
    sheet_name: str,
) -> list[dict[str, Any]]:

    df = pd.read_excel(
        path,
        sheet_name=sheet_name,
        header=None,
    )

    products: list[dict[str, Any]] = []

    product_rows = [
        row
        for row in range(len(df))
        if is_product_row(df, row)
    ]

    for index, product_row in enumerate(
        product_rows
    ):

        next_product_row = (
            product_rows[index + 1]
            if index + 1 < len(product_rows)
            else None
        )

        product = parse_product_block(
            df=df,
            product_row=product_row,
            next_product_row=next_product_row,
            sheet_name=sheet_name,
        )

        products.append(product)

    return products


# ---------------------------------------------------------
# Main importer
# ---------------------------------------------------------

def import_excel(
    input_path: Path,
    output_dir: Path,
) -> None:

    excel = pd.ExcelFile(
        input_path
    )

    print()
    print("Excel:", input_path)
    print("Sheets:")

    for sheet in excel.sheet_names:
        print(f"  - {sheet}")

    all_products: list[dict[str, Any]] = []

    for sheet_name in excel.sheet_names:

        print()
        print(
            f"Processing sheet: {sheet_name}"
        )

        products = parse_sheet(
            input_path,
            sheet_name,
        )

        print(
            f"  products: {len(products)}"
        )

        for product in products:

            print(
                f"    {product['name']}: "
                f"{len(product['variants'])} variants"
            )

        all_products.extend(
            products
        )

    # -----------------------------------------------------
    # products.json
    # -----------------------------------------------------

    products_path = (
        output_dir
        / "products.json"
    )

    save_json(
        products_path,
        all_products,
    )

    # -----------------------------------------------------
    # mixing_rules.json
    # -----------------------------------------------------

    mixing_rules: list[dict[str, Any]] = []

    for product in all_products:

        for variant in product["variants"]:

            mixing = variant.get(
                "mixing"
            )

            if not mixing:
                continue

            mixing_rules.append(
                {
                    "product": product["name"],
                    "technology": product[
                        "technology"
                    ],
                    "variant_id": variant[
                        "variant_id"
                    ],
                    "mixing": mixing,
                    "components": variant[
                        "components"
                    ],
                    "source": variant[
                        "source"
                    ],
                }
            )

    mixing_path = (
        output_dir
        / "mixing_rules.json"
    )

    save_json(
        mixing_path,
        mixing_rules,
    )

    # -----------------------------------------------------
    # calculations.json
    # -----------------------------------------------------

    calculations: list[dict[str, Any]] = []

    for product in all_products:

        for variant in product["variants"]:

            calculations.append(
                {
                    "product": product["name"],
                    "technology": product[
                        "technology"
                    ],
                    "variant_id": variant[
                        "variant_id"
                    ],
                    "price": variant[
                        "price"
                    ],
                    "coverage": variant[
                        "coverage"
                    ],
                    "calculation_reference": (
                        variant[
                            "calculation_reference"
                        ]
                    ),
                    "source": variant[
                        "source"
                    ],
                }
            )

    calculations_path = (
        output_dir
        / "calculations.json"
    )

    save_json(
        calculations_path,
        calculations,
    )

    # -----------------------------------------------------
    # Summary
    # -----------------------------------------------------

    print()
    print("=" * 60)
    print("IMPORT COMPLETE")
    print("=" * 60)

    print(
        f"Products:      {len(all_products)}"
    )

    print(
        f"Mixing rules:  {len(mixing_rules)}"
    )

    print(
        f"Calculations:  {len(calculations)}"
    )

    print()
    print(
        f"Products:      {products_path}"
    )

    print(
        f"Mixing rules:  {mixing_path}"
    )

    print(
        f"Calculations:  {calculations_path}"
    )


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Import Paint RAG Excel knowledge base"
        )
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Path to Excel file",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "data/knowledge"
        ),
        help="Output directory",
    )

    args = parser.parse_args()

    import_excel(
        input_path=args.input,
        output_dir=args.output,
    )


if __name__ == "__main__":
    main()
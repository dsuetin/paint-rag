from __future__ import annotations

import re
from typing import Any

from paint_rag.models.product import Product


ARTICLE_RE = re.compile(
    r"\b[A-Z]{2,5}\d{2,5}-[A-Z0-9]+\b",
    re.IGNORECASE,
)

CONSUMPTION_RE = re.compile(
    r"(?:до\s*)?(\d+(?:[.,]\d+)?)\s*[-–]\s*"
    r"(\d+(?:[.,]\d+)?)\s*гр\s*/\s*м[²2]",
    re.IGNORECASE,
)

LAYERS_RE = re.compile(
    r"(?:не\s+более|до)\s+(\d+)\s*",
    re.IGNORECASE,
)

HARDENER_RE = re.compile(
    r"([A-Z]{2,10}\d{2,5})\s+"
    r"(\d+(?:[.,]\d+)?)\s*%",
    re.IGNORECASE,
)

THINNER_RE = re.compile(
    r"(?:Разбавитель|Разбавитель\s+)"
    r"\s*(\d+(?:[.,]\d+)?)\s*[-–]\s*"
    r"(\d+(?:[.,]\d+)?)\s*%",
    re.IGNORECASE,
)


def clean(text: str | None) -> str:
    if not text:
        return ""

    return " ".join(text.split())


def to_float(value: str) -> float:
    return float(value.replace(",", "."))


def parse_technical_data(
    text: str,
    *,
    source: str | None = None,
) -> Product:

    text = clean(text)

    # -----------------------------------------------------
    # Article
    # -----------------------------------------------------

    article_match = ARTICLE_RE.search(text)

    if not article_match:
        raise ValueError(
            "Product article not found"
        )

    article = article_match.group(0).upper()

    # -----------------------------------------------------
    # Product name
    # -----------------------------------------------------

    # Для PA334 пока используем артикул как name.
    # Позже можно извлекать полноценное название
    # из технического листа.
    name = article

    # -----------------------------------------------------
    # Consumption
    # -----------------------------------------------------

    consumption_min = None
    consumption_max = None

    match = CONSUMPTION_RE.search(text)

    if match:
        consumption_min = to_float(
            match.group(1)
        )

        consumption_max = to_float(
            match.group(2)
        )

    # -----------------------------------------------------
    # Max layers
    # -----------------------------------------------------

    max_layers = None

    match = LAYERS_RE.search(text)

    if match:
        max_layers = int(
            match.group(1)
        )

    # -----------------------------------------------------
    # Hardener
    # -----------------------------------------------------

    hardener = None
    hardener_min = None

    match = HARDENER_RE.search(text)

    if match:
        hardener = match.group(1).upper()
        hardener_min = to_float(
            match.group(2)
        )

    # -----------------------------------------------------
    # Thinner
    # -----------------------------------------------------

    thinner = None
    thinner_min = None
    thinner_max = None

    match = THINNER_RE.search(text)

    if match:
        thinner = "Разбавитель"

        thinner_min = to_float(
            match.group(1)
        )

        thinner_max = to_float(
            match.group(2)
        )

    # -----------------------------------------------------
    # Mixing
    # -----------------------------------------------------

    mixing = None

    if hardener or thinner:

        mixing = {
            "base_ratio": 100.0,

            "hardener": hardener,

            "hardener_ratio": (
                {
                    "min": hardener_min,
                    "max": hardener_min,
                }
                if hardener_min is not None
                else None
            ),

            "thinner": thinner,

            "thinner_ratio": (
                {
                    "min": thinner_min,
                    "max": thinner_max,
                }
                if thinner_min is not None
                else None
            ),

            "total_ratio": None,

            "raw": text,
        }

    # -----------------------------------------------------
    # Product
    # -----------------------------------------------------

    return Product.model_validate(
        {
            "name": name,
            "article": article,
            "technology": None,
            "aliases": [],

            "consumption_min": consumption_min,
            "consumption_max": consumption_max,

            "max_layers": max_layers,

            "mixing": mixing,

            "variants": [],

            "source": {
                "type": "technical_data",
                "path": source,
            },
        }
    )
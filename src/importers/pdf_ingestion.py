"""Ingestion PDF-файлов (технические карточки) в нормализованный Product.

Парсер не завязан на конкретный продукт: информация извлекается
по смысловым паттернам (Артикул, Название, Пропорции смешивания,
Количество слоёв, Технические данные), без учёта фиксированной раскладки.
Если конкретного поля нет в документе — значение остаётся None:
ничего не выдумываем.
"""

from __future__ import annotations

import os
import re
from typing import Optional

from paint_rag.knowledge.technical_data_extractor import (
    extract_technical_data,
)
from paint_rag.models.product import (
    MixingComponent,
    MixingRule,
    Product,
    ProductSource,
)

_ARTICLE_RE = re.compile(
    # Три формы артикулов (без привязки к конкретным продуктам):
    #   1) Числовой (D-DUR/AkzoNobel): «2575-001251», «690-320001»
    #   2) Буквенный с дефисом (Rupa): «PV290-99», «PA777-9016», «PB420-XX»
    #   3) Буквенный с пробелом (Sikkens/Oswald): «WF 761», «WT 894»
    r"\b(?P<num>\d{4,6}-\d{4,6})\b"
    r"|\b(?P<letter>[A-Za-z]{1,5}\d{1,6}[-](?:\d{1,6}|[A-Za-z]{1,6}))\b"
    r"|\b(?P<space>[A-Za-z]{1,5}\s\d{1,5})\b"
)

_NUM = r"(\d+(?:[.,]\d+)?)"

_WORD_NUMBERS = {
    "один": 1,
    "одна": 1,
    "два": 2,
    "две": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
}

_TECH_FIELDS = (
    "gloss",
    "dry_residue",
    "density",
    "viscosity",
    "pot_life",
    "drying",
    "shelf_life",
    "application",
    "usage",
    "description",
)


def _read_pdf(path: str) -> tuple[str, int]:
    from pypdf import PdfReader

    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages), len(reader.pages)


def _collapse(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    # Склеиваем переносы слов с дефисом из PDF: «полиурета- новый».
    text = re.sub(r"(\w)- (\w)", r"\1\2", text)
    text = re.sub(r"(\w) - (\w)", r"\1\2", text)
    return text


def _find_article(text: str) -> Optional[str]:
    """Обобщаемый поиск артикула.

    Три формы (все независимы от конкретных продуктов):
      1) Числовой: 2575-001251, 690-320001 (D-DUR / AkzoNobel)
      2) Буквенный с дефисом: PV290-99, PA777-9016 (Rupa)
      3) Буквенный с пробелом: WF 761, WT 894 (Sikkens / Oswald)

    Возвращает первый найденный match, или None.
    """
    match = _ARTICLE_RE.search(text)
    if not match:
        return None
    # Порядок приоритета: num > letter > space.
    for name in ("num", "letter", "space"):
        group = match.group(name)
        if group is not None:
            return group
    return None


def _is_cyrillic_text(line: str) -> bool:
    letters = [c for c in line if c.isalpha()]
    if not letters:
        return False
    cyrillic = sum(
        "\u0400" <= c <= "\u04FF" or "\u0500" <= c <= "\u052F"
        for c in letters
    )
    return cyrillic > len(letters) / 2


def _find_name(text: str) -> Optional[str]:
    """Краткое название: короткая строка с буквами, стоящая до
    первого вхождения артикула; если такой строки нет — None (пусть
    вызывающий код возьмёт имя из имени файла)."""
    article = _ARTICLE_RE.search(text)
    if article is None:
        return None
    head = text[: article.start()]

    for line in head.splitlines():
        line = line.strip(" \t-–—")
        if not line or len(line) > 30:
            continue
        if re.search(r"\d{4}", line):
            continue
        if not _is_cyrillic_text(line):
            continue
        # Короткая строчка, похожая на имя продукта: без
        # двоеточия в конце (это метка «Технические данные:»,
        # «Время жизни смеси:» и т. п.), без точки в конце
        # (это часть предложения, а не заголовок), без «-» на
        # концах (это уже часть другого слова, обрезанного PDF).
        if line.endswith(":") or line.endswith("—"):
            continue
        return line
    return None


def _find_max_layers(text: str) -> Optional[int]:
    """Максимальное количество слоёв: максимум чисел перед словом
    «слой» («в два или три слоя», «наносить в 2 слоя», «2-3 слоя»)."""
    values: list[int] = []

    for match in re.finditer(
        r"((?:один|одна|два|две|три|четыре|пять|шесть|семь|восемь|девять|"
        + _NUM
        + r")\s+(?:и|или|и\s+)?\s*(?:один|одна|два|две|три|четыре|пять|"
        + _NUM
        + r")?)\s*[-–—]?\s*\d*\s*сло\w*",
        text,
        re.IGNORECASE,
    ):
        for token in match.group(1).split():
            if token in _WORD_NUMBERS:
                values.append(_WORD_NUMBERS[token])
            elif re.fullmatch(r"\d+(?:[.,]\d+)?", token):
                values.append(int(float(token.replace(",", "."))))

    for match in re.finditer(
        rf"({_NUM})\s*(?:и|или)\s*({_NUM})\s*сло\w*", text, re.IGNORECASE
    ):
        values.append(int(float(match.group(1).replace(",", "."))))
        values.append(int(float(match.group(2).replace(",", "."))))

    return max(values) if values else None


def _f(value: str) -> float:
    return float(value.replace(",", "."))


def _consumption_unit(text_after: str) -> Optional[str]:
    """Обобщающий распознаватель единицы расхода (м², л, мл...)."""
    t = text_after.lower()
    # Сначала специфичные (мл, л), потом обобщаящий «м²».
    if re.search(r"\bмл\s*/\s*м\s*²|\bмл/м2", t):
        return "ml_per_m2"
    if re.search(r"\bл\s*/\s*м\s*²|\bл/м2", t):
        return "l_per_m2"
    if re.search(r"м\s*²|м2", t):
        return "g_per_m2"
    return None


def _find_consumption(text: str) -> Optional[tuple[float, float, str]]:
    """Рекомендованный расход («до 120-140 гр/м²», «120–140 г/м²»,
    «Расход 60 - 80 мл/м²»).

    Обобщаемый: читает первое число после слова «расход». Диапазон
    «A–B» записывается (min=A, max=B); одиночное значение — в min и max.
    Возвращает None, если значения нет (не выдумываем).

    Важно: вызывать до ``_collapse(raw_text)`` — «60 - 80» превратится
    в «6080» и диапазон станет неразличим от единичного значения.
    """
    _INT = r"\d+(?:[.,]\d+)?"
    m = re.search(
        r"расх\w*\s*[:»]?\s*"
        r"(?:(?P<do>до)\s*)?"
        rf"(?P<lo>{_INT})"
        rf"(?:\s*[-–—]\s*(?P<hi>{_INT})|"
        r"\s*(?P<u>[^\n,]{0,20}))?",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    lo = _f(m.group("lo"))
    if m.group("hi") is not None:
        hi = _f(m.group("hi"))
        unit_after = text[m.end("hi") : m.end("hi") + 20]
    else:
        hi = lo
        unit_after = m.group("u") or ""
    unit = _consumption_unit(unit_after) or "g_per_m2"
    return lo, hi, unit


def _find_hardener(text: str) -> Optional[float]:
    """Отвердитель: «30 объемных частей отвердителя» / «отвердителя 30%»."""
    patterns = (
        r"(\d+(?:[.,]\d+)?)\s*(?:объемных\s*)?(?:част\w+\s*)*отвердителя",
        r"отвердителя\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*%",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _f(match.group(1))
    return None


def _find_thinner(text: str) -> Optional[object]:
    """Разбавитель: одиночное значение («30%») или диапазон («15–30%»)."""
    range_match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*[-–—]\s*(\d+(?:[.,]\d+)?)\s*%", text
    )
    if range_match:
        return (
            MixingComponent(
                percent_min=_f(range_match.group(1)),
                percent_max=_f(range_match.group(2)),
            )
        )

    percent = re.findall(r"(?<![\d.])\s*(\d+(?:[.,]\d+)?)\s*%", text)
    if percent:
        return MixingComponent(percent=_f(percent[0]))
    return None


def _find_making(text: str) -> Optional[MixingRule]:
    hardener = _find_hardener(text)
    thinner = _find_thinner(text)
    if hardener is None and thinner is None:
        return None
    return MixingRule(
        base_percent=100.0,
        hardener=(
            MixingComponent(percent=hardener)
            if hardener is not None
            else None
        ),
        thinner=thinner,
    )


def _normalize_name(name: str, text: str) -> str:
    """Акронимы бренда приводим к верхнему регистру, если в документе
    они встречаются в верхнем регистре; остальной текст — как есть."""
    tokens = []
    for token in name.split():
        upper = token.upper()
        if upper != token and re.search(re.escape(upper), text):
            tokens.append(upper)
        else:
            tokens.append(token)
    return " ".join(tokens)


def _find_technical_data(text: str):
    data = extract_technical_data(text)
    if any(getattr(data, field) is not None for field in _TECH_FIELDS):
        return data
    return None


def parse_pdf_to_product(path: str) -> Optional[Product]:
    """Извлекает нормализованный Product из PDF.

    Возвращает None, если файл не существует, не читается
    или в тексте не обнаружен артикул.
    """
    if not os.path.exists(path):
        return None

    raw_text, _ = _read_pdf(path)
    if not raw_text.strip():
        return None

    article = _find_article(raw_text)
    if article is None:
        return None

    text = _collapse(raw_text)

    name = _find_name(raw_text) or os.path.splitext(
        os.path.basename(path)
    )[0]
    name = _normalize_name(name, raw_text)

    making = _find_making(text)

    consumption = _find_consumption(raw_text)

    return Product(
        name=name,
        article=article,
        consumption_min=consumption[0] if consumption else None,
        consumption_max=consumption[1] if consumption else None,
        consumption_unit=consumption[2] if consumption else None,
        technology=(
            "2K-полиуретановый"
            if re.search(
                r"двухкомпонентн\w+|polyurethane", text, re.IGNORECASE
            )
            else None
        ),
        max_layers=_find_max_layers(text),
        mixing=making,
        technical_data=_find_technical_data(raw_text),
        source=ProductSource(
            file=os.path.basename(path),
            page=1,
            sheet=None,
        ),
    )

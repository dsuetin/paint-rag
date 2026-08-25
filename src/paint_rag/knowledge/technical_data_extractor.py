from __future__ import annotations

import re
from typing import Optional

from paint_rag.models.product import TechnicalData


# Field -> synonymous RU/EN label terms (most specific first).
# Terminology dictionary — not bound to filename/product name.
_FIELD_LABELS: list[tuple[str, tuple[str, ...]]] = [
    (
        "gloss",
        ("степень блеска", "степеньглянца", "блеск", "gloss"),
    ),
    (
        "dry_residue",
        (
            "сухой остаток",
            "массовая доля нелетучих",
            "доля нелетучих",
            "dry residue",
            "solid content",
        ),
    ),
    (
        "density",
        ("плотность", "удельный вес", "density", "specific weight"),
    ),
    (
        "viscosity",
        ("вязкость", "viscosity"),
    ),
    (
        "pot_life",
        (
            "время жизни смеси",
            "время жизни",
            "жизнеспособность",
            "pot life",
        ),
    ),
    (
        "drying",
        (
            "время сушки",
            "время высыхания",
            "высыхание",
            "drying time",
        ),
    ),
    (
        "shelf_life",
        ("срок годности", "срок хранения", "shelf life"),
    ),
    (
        "application",
        ("способ нанесения", "нанесение", "application"),
    ),
    (
        "usage",
        (
            "область применения",
            "назначение",
            "применение",
            "usage",
        ),
    ),
    (
        "description",
        (
            "описание продукта",
            "описание материала",
            "описание",
            "description",
        ),
    ),
]

# «Длинные» текстовые поля: значение может продолжать соседние строки.
_LONG_TEXT_FIELDS = frozenset({"application", "usage", "description"})

# Сколько слов допустимо до метки (чтобы отличать строку-характеристику
# от упоминания термина внутри прозы).
_MAX_WORDS_BEFORE_LABEL = 2

# Разделители между меткой и значением в одной строке.
_SEPARATOR_RE = re.compile(r"[\s\-–—:,]+")

# Строки, начинающие новую характеристику (метка + разделитель).
_VALUE_ROW_RE = re.compile(
    r"(степень блеска|степеньглянца|сухой остаток|массовая доля"
    r"|плотность|вязкость|время жизни|время сушки|время высыхания"
    r"|срок годности|срок хранения|способ нанесения|нанесение"
    r"|область применения|назначение|описание)"
    r"[\s\-–—:,]"
)

# Строки, «закрывающие» текущее поле.
_STOP_STRICT = (
    "примечания",
    "техника безопасности",
    "пропорции смешивания",
    "отвердитель",
    "разбавитель",
    "дополнительная информация",
    "рекомендованный расход",
    "рекомендованное количество",
    "паспорт",
    "безопасность",
    "тщательно перемешать",
    "очищайте инструмент",
    "хранить в плотно закрытой",
    "средства индивидуальной",
    "рабочие помещения",
    "ознакомьтесь с",
    "паспортом безопасности",
    "альтернативные отвердители",
    "альтернативный отвердитель",
    "источник",
    "производитель",
)


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------

def _norm(value: Optional[str]) -> str:
    if value is None:
        return ""
    value = re.sub(r"\s+", " ", value).strip()
    # Склеиваем переносы слов с дефисом: «барьер- ный» -> «барьерный».
    value = re.sub(r"(\w)-\s(\w)", r"\1\2", value)
    return value


def _word_count_before(line: str, idx: int) -> int:
    return len(line[:idx].split())


def _is_bullet(line: str) -> bool:
    return bool(line) and line[0] in "џ•◦-*–—\t"


def _is_heading(line: str) -> bool:
    """Заголовок: все буквы (кроме цифр/знаков) — заглавные."""
    letters = [c for c in line if c.isalpha()]
    if len(letters) < 2:
        return False
    return all(c.isupper() for c in letters)


def _is_stop_line(line: str) -> bool:
    low = line.lower().strip()

    if not low:
        return True

    if _is_bullet(line):
        return True

    # Заголовок определяется по регистру, поэтому проверяем исходную строку.
    if _is_heading(line.strip()):
        return True

    if any(low.startswith(stop) for stop in _STOP_STRICT):
        return True

    if _VALUE_ROW_RE.search(low):
        return True

    return False


def _match_label(line: str) -> Optional[tuple[str, str]]:
    low = line.lower()
    best: Optional[tuple[str, str]] = None
    best_len = -1

    for field, labels in _FIELD_LABELS:
        for label in labels:
            idx = low.find(label.lower())
            if idx == -1:
                continue
            if _word_count_before(line, idx) > _MAX_WORDS_BEFORE_LABEL:
                continue
            if len(label) > best_len:
                best_len = len(label)
                best = (field, label)

    return best


# ------------------------------------------------------------------
# capture
# ------------------------------------------------------------------

def _inline_value(line: str, label: str) -> Optional[str]:
    """Значение, стоящее после метки в той же строке."""
    idx = line.lower().find(label.lower())
    if idx == -1:
        return None

    after = line[idx + len(label):]
    stripped = _SEPARATOR_RE.sub("", after, count=1)

    if not stripped:
        return None

    # «Вязкость смеси Din 4:» / «Нанесение:» -> значения в этой строке нет.
    if stripped.endswith(":"):
        return None

    # «Время сушки при 23оС: до 12 часов» -> «до 12 часов».
    if ":" in stripped:
        stripped = stripped.rsplit(":", 1)[-1].strip()

    if not stripped:
        return None

    if stripped.endswith((".", ",")):
        stripped = stripped[:-1].strip()

    return stripped or None


def _label_continues(lines: list[str], index: int, label: str | None = None) -> bool:
    """Метка разбита на несколько строк.

    Признак: значения в строке метки нет, а следующая строка
    заканчивается двоеточием и сама не является строкой-характеристикой.
    """
    if label is not None and _inline_value(lines[index], label) is not None:
        return False

    nxt = index + 1
    if nxt >= len(lines):
        return False

    if not lines[nxt].rstrip().endswith(":"):
        return False

    return _match_label(lines[nxt]) is None


def _next_value_index(lines: list[str], index: int) -> Optional[int]:
    """Индекс первой строки со значением, пропуская продолжение метки."""
    j = index + 1
    while j < len(lines) and lines[j].rstrip().endswith(":"):
        j += 1

    if j >= len(lines):
        return None

    if _is_stop_line(lines[j]):
        return None

    return j


def _capture_short(lines: list[str], index: int, label: str) -> Optional[str]:
    # 1) Значение в той же строке.
    inline = _inline_value(lines[index], label)

    # 2) Метка разбита на несколько строк: берём значение после последней
    #    строки с двоеточием.
    if _label_continues(lines, index, label):
        value_idx = _next_value_index(lines, index)
        if value_idx is not None:
            return _norm(lines[value_idx])
        if inline is not None:
            return _norm(inline)
        return None

    # 3) Иначе — значение либо в строке метки, либо на следующей строке.
    if inline is not None:
        return _norm(inline)

    value_idx = _next_value_index(lines, index)
    if value_idx is not None:
        return _norm(lines[value_idx])

    return None


def _capture_long(lines: list[str], index: int, label: str) -> Optional[str]:
    """Текстовое поле: метка + (необязательно) значение в строке +
    дописывание соседних строк до первого стоп-условия (заголовок,
    новая характеристика, пункт предостережения)."""
    inline = _inline_value(lines[index], label)

    parts: list[str] = []

    if inline is not None:
        parts.append(inline)

    j = index + 1

    cap = 3

    while j < len(lines) and len(parts) < (3 if inline is None else cap + 1):
        if _is_stop_line(lines[j]):
            break
        if _label_continues(lines, j):
            break
        parts.append(lines[j])
        j += 1
        if len(parts) >= 3:
            break

    value = " ".join(parts)
    return _norm(value) or None


def extract_technical_data(text: str) -> TechnicalData:
    if not text or not text.strip():
        return TechnicalData()

    lines = [_norm(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    data = TechnicalData()
    filled: set[str] = set()

    for index, line in enumerate(lines):
        match = _match_label(line)
        if match is None:
            continue

        field, label = match

        if field in filled:
            continue

        if field in _LONG_TEXT_FIELDS:
            value = _capture_long(lines, index, label)
        else:
            value = _capture_short(lines, index, label)

        if value:
            setattr(data, field, value)
            filled.add(field)

    return data


def extract_technical_data_from_pdf(
    path: str,
    max_pages: Optional[int] = None,
) -> TechnicalData:
    from pypdf import PdfReader

    reader = PdfReader(path)
    pages = reader.pages

    if max_pages is not None:
        pages = pages[:max_pages]

    text = "\n".join((page.extract_text() or "") for page in pages)
    return extract_technical_data(text)

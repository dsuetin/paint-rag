from __future__ import annotations

import re
from typing import Optional

from paint_rag.models.product import TechnicalData


# Field -> synonymous RU/EN label terms.
# Terminology dictionary — not bound to filename/product name.
_FIELD_LABELS: list[tuple[str, tuple[str, ...]]] = [
    (
        "gloss",
        ("степень блеска", "степеньглянца", "степень глянца", "блеск", "gloss"),
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
_SEPARATORS = " \t-–—:,"

# Фразы, «закрывающие» текущее поле (пункты предостережения,
# примечания, новые разделы).
_STOP_PHRASES = (
    "примечание",
    "применение, эксплуатация",
    "применение эксплуатация",
    "техника безопасности",
    "пропорции смешивания",
    "отвердитель",
    "разбавитель",
    "дополнительная информация",
    "рекомендованный расход",
    "рекомендованное количество",
    "рекомендуемый расход",
    "рекомендуемое количество",
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
    "ооо",
)

# Значение может содержать слова (например «до 12 часов»),
# но НЕ может содержать цифру после двоеточия, когда метка
# разбита на строки.
_LEADING_NUM_RE = re.compile(r"^\s*-?(\s*|\d)")


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


def _contains_label(line: str) -> bool:
    low = line.lower()
    for _field, labels in _FIELD_LABELS:
        for label in labels:
            if label in low:
                return True
    return False


def _is_stop_line(line: str) -> bool:
    low = line.lower().strip(" \t")
    if not low:
        return True
    if _is_bullet(line):
        return True
    # Заголовок определяется по регистру, поэтому проверяем исходную строку.
    if _is_heading(line.strip()):
        return True
    if any(low.startswith(stop) for stop in _STOP_PHRASES):
        return True
    if _contains_label(line):
        return True
    return False


_LABEL_SEPARATORS = " \t-–—:,"


def _label_starts_line(line: str, label: str) -> bool:
    low = line.lower()
    idx = low.find(label.lower())
    if idx == -1:
        return False
    if idx == 0:
        return True
    return low[idx - 1] in _LABEL_SEPARATORS


def _next_label_boundary(line: str, start: int) -> int:
    """Позиция следующей метки характеристики внутри строки
    (после start), или -1.  Используется, чтобы не забирать
    соседние поля в одно значение («...48±2%. Плотность - 1,10...»)."""
    low = line.lower()
    boundary = -1
    for _field, labels in _FIELD_LABELS:
        for label in labels:
            for search in (low[start:], low):
                offset = start if search is low[start:] else 0
                rest = search.find(label.lower())
                if rest == -1:
                    continue
                pos = offset + rest
                if pos < start:
                    continue
                # Метка начинается новое слово: перед ней пробел,
                # пунктуация или тире («...±2%. Плотность - ...»).
                if pos > 0 and low[pos - 1] not in " \t.,:;–—-":
                    continue
                if boundary == -1 or pos < boundary:
                    boundary = pos
                break
    return boundary


def _match_label(line: str) -> Optional[tuple[str, str]]:
    """Метку считаем подходящей только если она начинается строку
    (или идёт после разделителя).  Это отличает строку-характеристику
    от термина внутри прозы — например, «время высыхания» внутри
    фразы «Время высыхания или полировки ...»."""
    low = line.lower()
    best: Optional[tuple[str, str]] = None
    best_len = -1

    for field, labels in _FIELD_LABELS:
        for label in labels:
            if not _label_starts_line(line, label):
                continue
            if _word_count_before(line, low.find(label.lower())) > _MAX_WORDS_BEFORE_LABEL:
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

    value_start = idx + len(label)

    # Значение обрывается на следующей метке характеристики
    # («Сухой остаток - 48±2%. Плотность - 1,10...»).
    boundary = _next_label_boundary(line, value_start)
    if boundary != -1:
        after = line[value_start:boundary]
    else:
        after = line[value_start:]

    # «Вязкость смеси Din 4:» -> значения нет.
    stripped = after.lstrip(_SEPARATORS)

    if not stripped:
        return None

    # «Время сушки при 23оС: до 12 часов» -> «до 12 часов».
    if ":" in stripped:
        stripped = stripped.rsplit(":", 1)[-1].strip()

    if not stripped:
        return None

    stripped = stripped.strip()

    if stripped and stripped[-1] in (".", ","):
        stripped = stripped[:-1].strip()

    return stripped or None


def _has_digit(value: str) -> bool:
    return any(c.isdigit() for c in value)


def _capture_short(lines: list[str], index: int, field: str, label: str) -> Optional[str]:
    inline = _inline_value(lines[index], label)

    # Хэштег (короткое) значение всегда содержит число/единицу
    # («54±2%», «3 часа», «от 12 месяцев»).  Если после метки стоит
    # только фрагмент прозы («или полировки»), это продолжение
    # самой метки, а не значение.
    if inline is not None and _has_digit(inline):
        return _norm(inline)

    # Метка без значения в строке. Варианты:
    #   «Вязкость смеси Din 4:»
    #   «70±10»
    #   «Время высыхания или полировки
    #    после нанесения второго слоя:
    #    24 часа»
    # Блок значения — подряд стоящие строки без цифр и без
    # стоп-признаков, оканчивающиеся строкой с цифрой.
    j = index + 1
    block: list[str] = []
    value: Optional[str] = None

    while j < len(lines):
        line = lines[j]

        # Строка, оканчивающаяся двоеточием — продолжение метки,
        # а не значение.  Значения стоят на следующей строке.
        if line.rstrip().endswith(":"):
            block.append(line)
            j += 1
            continue

        if _is_stop_line(line):
            break

        if _LEADING_NUM_RE.match(line):
            candidate = _norm(line)
            if candidate.endswith((".", ",")):
                candidate = candidate.rstrip(".,").strip()
            if candidate:
                value = candidate
            break

        block.append(line)
        j += 1

        if len(block) > 6:
            break

    if value is None:
        # Значение могло быть на строке сразу после блока метки
        # без двоеточия-разделителя.
        j2 = index + 1 + len(block)
        if j2 < len(lines) and _LEADING_NUM_RE.match(lines[j2]):
            value = _norm(lines[j2])

    return value


def _capture_long(lines: list[str], index: int, field: str, label: str) -> Optional[str]:
    """Текстовое поле: метка + (необязательно) значение в строке +
    дописывание соседних строк до первого стоп-условия (заголовок,
    новая характеристика, пункт предостережения)."""
    inline = _inline_value(lines[index], label)

    parts: list[str] = []

    if inline is not None:
        parts.append(inline)

    j = index + 1

    while j < len(lines):
        line = lines[j]

        if _is_stop_line(line):
            break

        parts.append(line)
        j += 1

    value = " ".join(p for p in parts if p)
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
            value = _capture_long(lines, index, field, label)
        else:
            value = _capture_short(lines, index, field, label)

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

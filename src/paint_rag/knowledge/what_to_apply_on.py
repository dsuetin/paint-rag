"""Парсер и модель «Что на что можно наносить» (STAINWOOD).

Главный исходник задачи: ``data/STAINWOOD/Схемы/Что на что можно наносить.txt``.

Суть документа
==============
Документ — это **матрица совместимости ХИМИЧЕСКИХ СИСТЕМ** (NC/AC/PU/PE/UV/WB),
а НЕ таблица «конкретный продукт → конкретный продукт». В файле нет НИ ОДНОГО
артикула, кроме единственного **исключения** в примечании:

    568-46312 Аква Тэк Сурф → Профф 355

Поэтому «перенос зависимостей в products.json» возможен только для того
исключения. Все остальные 25 зависимостей имеют **уровень ХИМИИ** и уже
корректно хранятся в ``data/knowledge/compatibility.json`` (25 пар,
17 allowed / 8 forbidden).

Направление («X на Y»)
======================
«**X на Y**» = «X наносится **НА** Y» = **X — верхний слой (top)**, **Y —
нижний слой (base)**. Подтверждается примечаниями, напр. для «NC на WB»:
    «Активный растворитель **NC** слоя может вызвать вспучивание **WB** покрытия»
(верхний NC реагирует с нижним WB). В модели :class:`ProductRelation` это
``top=X, base=Y``.

Что НЕ делаем (по т.з. §Важно, 5, 7, 11)
========================================
* Не выводим совместимость по хим. составу / типу ЛКМ / названию / «похожему
  артикулу» / «обычно так делают».
* Не поднимаем химические коды NC/AC/… до конкретных артикулов: такое
  сопоставление НЕОДНОЗНАЧНО (напр. «PU» совпадает с ~10 продуктами по
  названию, а по артикулу — с 0). Такие записи → ``UNRESOLVED`` (не
  создаём связь).
* Не превращаем рецептуры смешивания / отвердители / разбавители в
  compatibility.
* Отсутствие строки/связи = ``UNKNOWN`` (НЕ ``FORBIDDEN``).

Примечание о парсинге
======================
``.txt`` — распечатка графической матрицы (символы ✓/✗ из Wingdings потеряны
в плоском тексте). Тем не менее **набор из 25 пар**, **примечания** и
**единственное артикульное исключение** извлекаются детерминированно.
ALLOWED / FORBIDDEN для каждой конкретной пары НЕ «вычитается» из повреждённых
символов (это было бы гаданием); он хранится в согласованном с документом
``compatibility.json`` (тот же набор пар).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Химические коды, встречающиеся в документе.
CHEMISTRY_CODES = ("NC", "AC", "PU", "PE", "UV", "WB")

# Символы-«галочка/крестик» (Wingdings), которые встречаются в .txt.
_CHECK = "\uf04a"
_CROSS = "\uf04c"

_RE_PAIR = re.compile(r"^([A-Z]{2})\s+на\s+([A-Z]{2})$")
# «…(кроме 568-46312 Аква Тэк Сурф поверх которого можно наносить Профф 355).»
# group 1 — артикул; group 2 — название base; group 3 — название top.
# Название base заканчивается перед словом «поверх» (жадное до «поверх»).
_RE_EXCEPTION = re.compile(
    r"кроме\s+([\d\-]+)"                          # group1: 568-46312
    r"\s+([А-ЯЁ][а-яё0-9]+(?:\s+[А-ЯЁ]?[а-яё0-9]+)*?)"  # group2: name base
    r"\s+поверх\s+которого\s+можно\s+наносить"
    r"\s+([А-ЯЁ][а-яё0-9]+(?:\s+[А-ЯЁ]?[а-яё0-9]+)*)"   # group3: top name
)

_SOURCE_FILE = (
    "data/STAINWOOD/Схемы/Что на что можно наносить.txt"
)


@dataclass
class FamilyPair:
    """Одна явная зависимость «X на Y» из матрицы химии.

    ``top``  — верхний слой (то, что наносят) — **X** в «X на Y».
    ``base`` — нижний слой (то, на что наносят) — **Y** в «X на Y».

    ``status``: ``ALLOWED`` (✓) / ``FORBIDDEN`` (✗) / ``UNKNOWN``. Поскольку
    в упрощённом .txt символы потеряны, здесь значение по умолчанию
    ``UNKNOWN`` и его **НЕ** разрешено трактовать как запрет.
    """

    top: str
    base: str
    status: str = "UNKNOWN"
    note: str | None = None

    @property
    def level(self) -> str:
        return "CHEM"  # уровень химии, НЕ артикул


@dataclass
class ArticleRelation:
    """Единственная АРТИКУЛЬНАЯ зависимость, встречающаяся в документе.

    ``base_article`` = 568-46312 (Аква Тэк Сурф) — то, НА что можно наносить.
    ``top``          = Профф 355 — то, что можно наносить поверх.
    ``status`` = ``ALLOWED`` (документ явно: «можно наносить»).
    """

    base_article: str
    base_name: str
    top: str
    status: str = "ALLOWED"
    note: str = (
        "кроме 568-46312 Аква Тэк Сурф поверх которого можно наносить Профф 355"
    )

    @property
    def level(self) -> str:
        return "ART"


@dataclass
class UnresolvedMapping:
    """Зависимость, которую НЕ удалось однозначно сопоставить с продуктом:
    связь НЕ создаётся, запись фиксируется (т.з. п.7, 11.5)."""

    kind: str  # "FAMILY" | "ARTICLE"
    label: str
    reason: str
    relation: "FamilyPair | ArticleRelation | None" = None


class WhatToApplyOnSource:
    """Парсер и «source of truth» для документа.

    Детерминированно извлекает: *набор* из 25 пар химии, примечания и
    единственное артикульное исключение. ALLOWED/FORBIDDEN для каждой пары НЕ
    вычитается из повреждённых в .txt символов (иначе получалось бы гадание);
    он хранится в согласованном с документом ``compatibility.json`` (тот же
    набор из 25 пар, 17 allowed / 8 forbidden, направление top/base сохранено).
    """

    def __init__(self, path: str | Path = _SOURCE_FILE):
        self.path = Path(path)
        self.family_pairs: list[FamilyPair] = []
        self.article_relations: list[ArticleRelation] = []
        self.notes: list[str] = []
        self.legends: list[str] = []
        self.unresolved: list[UnresolvedMapping] = []
        if self.path.exists():
            self._parse(self.path.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    def _parse(self, text: str) -> None:
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith(_CHECK) or line.startswith(_CROSS):
                continue
            pair = _RE_PAIR.match(line)
            if pair:
                a, b = pair.group(1), pair.group(2)
                # «X на Y»: X = верхний (top), Y = нижний (base).
                self.family_pairs.append(FamilyPair(top=a, base=b))
                continue
            note_match = _RE_EXCEPTION.search(line)
            if note_match:
                base_article = note_match.group(1).strip()
                base_name = f"{base_article} {note_match.group(2).strip()}".strip()
                top = note_match.group(3).strip()
                self.article_relations.append(
                    ArticleRelation(
                        base_article=base_article,
                        base_name=base_name,
                        top=top,
                        status="ALLOWED",
                        note=line,
                    )
                )
                continue
            low = line.lower()
            if any(
                f"{c} -" in low or f"{c}-" in low
                for c in CHEMISTRY_CODES
            ) or "нитроцеллюлоз" in low or "водоразбавим" in low:
                self.legends.append(line)
                continue
            if len(line) > 12:
                self.notes.append(line)

    # ------------------------------------------------------------------
    # Сопоставление с продуктом (ТОЛЬКО точное совпадение артикула/алиаса)
    # ------------------------------------------------------------------
    def map_article_to_product(
        self, article: str, store
    ) -> "tuple[str, object]":
        """Вернуть ``("MAPPERED", product)`` или ``("UNRESOLVED", None)``.

        Только точное совпадение артикула/варианта/алиаса — **без**
        расширения по химии (т.з. «никаких догадок по хим. составу/типу ЛКМ»).
        """
        article_l = article.strip().lower()
        for product in store.products:
            if product.article and product.article.lower() == article_l:
                return "MAPPERED", product
            for pv in product.variants:
                if pv.article and pv.article.lower() == article_l:
                    return "MAPPERED", product
            for al in product.aliases:
                if al.lower() == article_l:
                    return "MAPPERED", product
        return "UNRESOLVED", None

    # ------------------------------------------------------------------
    def summarize(self) -> dict:
        return {
            "source_file": str(self.path),
            "family_pair_count": len(self.family_pairs),
            "article_relation_count": len(self.article_relations),
            "article_relations": [
                {
                    "base": a.base_name,
                    "base_article": a.base_article,
                    "top": a.top,
                    "status": a.status,
                }
                for a in self.article_relations
            ],
        }


def load_default() -> WhatToApplyOnSource:
    return WhatToApplyOnSource()


__all__ = [
    "CHEMISTRY_CODES",
    "FamilyPair",
    "ArticleRelation",
    "UnresolvedMapping",
    "WhatToApplyOnSource",
    "load_default",
]

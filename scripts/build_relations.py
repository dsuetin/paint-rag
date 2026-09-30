#!/usr/bin/env python3
"""Backfill products/relations/systems for Iteration 2.

Создаёт/обновляет:
* ``data/knowledge/product_relations.json``
* ``data/knowledge/coating_systems.json``

НЕ выдумывает данных — все связи из **источников**:
* product_relations.json — TД (PDF) с явной строкой
  «Подлежащий Праймер: Д-дур грунт» (Эмаль Д-дур база 01
  2675-755251, D-DUR 1149).
* coating_systems.json — из трёх таблиц «Системы нанесения» Excel
  (``data/STAINWOOD/Схемы/Системы нанесения.xlsx``, листы Т1, Т2, Т3)
  + из PDF «Holzhaus для рассылки.pdf» (стр. 50 — «Примеры
  систем под кисть»).

Запуск::

    ./.venv/bin/python scripts/build_relations.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE = ROOT / "data" / "knowledge"
SHEET1 = ROOT / "data/STAINWOOD/Схемы/Системы нанесения.xlsx"
HOZZ = ROOT / "data/STAINWOOD/Holzhaus для рассылки.pdf"


# ----------------------------------------------------------------------
# product_relations.json — ТД
# ----------------------------------------------------------------------


def build_product_relations() -> list[dict]:
    """Продуктовые правила, подтверждённые ПДФ-ТД.

    * Эмаль Д-ДУР база 01 (2675-755251) — «Подлежащий Праймер:
      Д-дур грунт» → base=D-DUR 1149, top=2675-755251, allowed=True.
    """
    return [
        {
            "base": "1149",            # Д-дур грунт (265-750001)
            "top": "2675-755251",     # Эмаль Д-дур база 01
            "allowed": True,
            "status": "CONFIRMED",
            "reason": "ТД эмаль Д-дур 01 напрямую указывает "
                      "«Подлежащий Праймер: Д-дур грунт».",
            "conditions": [],
            "source": {
                "file": "Эмаль Д-Дур база 01 полумат.pdf",
                "sheet": "AkzoNobel Д-Дур",
                "row": None,
                "product": "2675-755251",
                "note": "строчка «Подлежащий Праймер: Д-дур грунт, "
                        "УС грунт» из TД эмаль Д-дур база 01 "
                        "2675-755251.",
            },
        },
    ]


# ----------------------------------------------------------------------
# coating_systems.json — Т1/T2/T3 «Системы нанесения» + PDF Holzhaus
# ----------------------------------------------------------------------

# Т3 columns → нормализованные подложки (из заголовка Excel).
T3_COLUMNS = {
    1: "door_furniture_veneer_wood_solid",   # Двери/мебель/фасады (шпонированные, массив)
    2: "door_furniture_mdf",                  # Двери/мебель/фасады (МДФ)
    3: "table_table_top",                     # Столы/столешницы
    4: "chair",                               # Стулья
    5: "outdoor_window_furniture_door",       # Окна/мебель/двери (уличные)
    6: "stair",                               # Лестницы
}

T3_SUBSTRATE_LABELS = {
    "door_furniture_veneer_wood_solid": "Двери/мебель/фасады (шпонированные/массив)",
    "door_furniture_mdf": "Двери/мебель/фасады (МДФ)",
    "table_table_top": "Столы/столешницы",
    "chair": "Стулья",
    "outdoor_window_furniture_door": "Окна/мебель/двери (уличные)",
    "stair": "Лестницы",
}


def _cell(ws, row: int, col: int):
    v = ws.cell(row=row, column=col).value
    return None if v is None else str(v).strip()


def _is_yes(cell: str | None) -> bool:
    if cell is None:
        return False
    c = cell.strip().lower()
    return c in {"+", "да", "yes", "true", "v", "✓", "x"}


def _classify_layer_role(part: str) -> str:
    """Определить роль слоя по названию продукта (из ТД, только по смыслу)."""
    low = part.lower()
    if any(k in low for k in ("изолят", "силер")):
        return "isolator"
    if any(k in low for k in ("грунт", "праймер")):
        return "primer"
    # Финиш — всё, что после грунт/изолятор (лак или краска / эмаль).
    if any(k in low for k in ("краска", "эмаль", "лак", "профф", "усл",
                                "интрос", "ил-500", "ил-735", "спидлай",
                                "пластовфикс", "данныспид")):
        if "лак" in low or "паркетн" in low or "ил-" in low:
            return "topcoat (лак)"
        return "topcoat (краска)"
    return "component"


def _parse_systems_t1(ws) -> dict[str, dict]:
    """Т1: Название системы | Материалы, входящие в систему."""
    out: dict[str, dict] = {}
    for r in range(2, ws.max_row + 1):
        name = _cell(ws, r, 1)
        materials = _cell(ws, r, 2)
        if not name or not materials or name.lower().startswith("название"):
            continue  # пропускаем заголовок
        # Разбиваем только по «+» (имена продуктов могут содержать пробелы).
        parts = [p.strip() for p in materials.split("+") if p.strip()]
        layers = []
        for p in parts:
            # Артикул/номер — последняя группка цифр (например, «110.04»).
            article = None
            m = re.search(r"(\d+(?:[.,]\d+)+)", p)
            if m:
                article = m.group(1)
            layers.append(
                {
                    "role": _classify_layer_role(p),
                    "name": p,
                    "article": article,
                }
            )
        out[name] = {
            "name": name,
            "materials_text": materials,
            "layers": layers,
        }
    return out


def _parse_systems_t2(ws) -> dict:
    """Т2: Название системы | Достоинства | Недостатки | Типы изделий."""
    out = {}
    for r in range(2, ws.max_row + 1):
        name = _cell(ws, r, 1)
        if not name:
            continue
        out[name] = {
            "advantages": _cell(ws, r, 2),
            "disadvantages": _cell(ws, r, 3),
            "item_types_text": _cell(ws, r, 4),
        }
    return out


def _parse_substrates_from_t3(ws) -> dict:
    """Т3: Название системы | 6 колонок (подложка/изделие).

    Возвращает {name: {substrate: bool}}.
    """
    out = {}
    for r in range(2, ws.max_row + 1):
        name = _cell(ws, r, 1)
        if not name:
            continue
        subs = {}
        for col_idx, key in T3_COLUMNS.items():
            subs[key] = _is_yes(_cell(ws, r, col_idx + 1))
        out[name] = subs
    return out


def _parse_holzhau_examples() -> list[dict]:
    """PDF «Примеры систем под кисть» (стр. 50).

    Только явные системы из TД:
    * «Cetol WP 567BPD/Axil2000 + 3xCetol WF771» (тонкослойная);
    * «Cetol WP 567BPD/Axil2000 + 3xCetol WF9810-46-25» (среднеслойная);
    * «Cetol WP 567BPD/Axil2000 + 3xRubbol WF3310-06-25» (среднеслойная).
    """
    base_ref = "Cetol WP 567BPD/Axil2000"
    base_layer = {
        "role": "antiseptic + primer (грунт-антисептик + грунт)",
        "name": base_ref,
        "article": None,
    }
    return [
        {
            "name": "Cetol тонкослойная 1-компонентная (567/567+Axil → WF771)",
            "materials_text": "Cetol WP 567BPD / Axil 2000 + 3×Cetol WF771",
            "layers": [
                base_layer,
                {"role": "topcoat (лак)", "name": "Cetol WF771",
                 "article": "WF771", "layers_count": 3},
            ],
            "status": "CONFIRMED",
            "source": {
                "file": "Cetol 771", "sheet": None,
                "note": "«Примеры систем под кисть» — тонкослойная "
                        "система: 567/Axil2000 + 3×WF771 (стр. 50).",
            },
        },
        {
            "name": "Cetol среднеслойная (567/567+Axil → WF9810-46-25)",
            "materials_text": "Cetol WP 567BPD / Axil 2000 + 3×Cetol WF9810-46-25",
            "layers": [
                base_layer,
                {"role": "topcoat (лак)", "name": "Cetol WF9810-46-25",
                 "article": "WF 9810-46-25", "layers_count": 3},
            ],
            "status": "CONFIRMED",
            "source": {
                "file": "Паспорт 567.pdf", "sheet": None,
                "note": "«Примеры систем под кисть» — среднеслойная "
                        "система: 567/Axil2000 + 3×WF9810-46-25 (стр. 50).",
            },
        },
        {
            "name": "Cetol среднеслойная (567/567+Axil → Rubbol WF3310-06-25)",
            "materials_text": "Cetol WP 567BPD / Axil 2000 + 3×Rubbol WF3310-06-25",
            "layers": [
                base_layer,
                {"role": "topcoat (краска)", "name": "Rubbol WF3310-06-25",
                 "article": "WF 3310-06-25", "layers_count": 3},
            ],
            "status": "CONFIRMED",
            "source": {
                "file": "Rubbol WF3310", "sheet": None,
                "note": "«Примеры систем под кисть» — среднеслойная "
                        "система: 567/Axil2000 + 3×WF3310 (стр. 50).",
            },
        },
    ]


def build_coating_systems():
    """Объединённый набор coating systems из Excel Т1/T2/T3 (+PDF опц.).

    Возвращает tuple (excel_systems, holzhau_systems, meta).
    """
    # Excel
    wb = openpyxl.load_workbook(SHEET1, data_only=True)
    t1: dict[str, dict] = _parse_systems_t1(wb["Таблица1"])
    t2: dict[str, dict] = _parse_systems_t2(wb["Таблица2"])
    t3: dict[str, dict] = _parse_substrates_from_t3(wb["Таблица3"])

    excel_systems = []
    for name, spec in t1.items():
        subs_meta = t3.get(name, {})
        # substrates — machine-ключи Т3 (door_furniture_mdf и т.д.).
        substrates = [
            key for key, allowed in subs_meta.items() if allowed
        ]
        substrate_labels = [
            T3_SUBSTRATE_LABELS[key]
            for key in substrates
            if key in T3_SUBSTRATE_LABELS
        ]
        excel_systems.append({
            "name": name,
            "materials_text": spec["materials_text"],
            "layers": spec["layers"],
            "substrates": substrates,
            "substrate_labels": substrate_labels,
            "advantages": t2.get(name, {}).get("advantages"),
            "disadvantages": t2.get(name, {}).get("disadvantages"),
            "status": "CONFIRMED",
            "item_types": t2.get(name, {}).get("item_types_text"),
            "source": {
                "file": str(SHEET1),
                "sheet": "Таблица1/Таблица2/Таблица3",
                "row": _find_row(t1, name, wb),
                "note": "Т1: материалы в системе; Т2: преимущества/"
                        "недостатки/типы изделий; Т3: матрица "
                        "«система × подложка» (+ = допустима).",
            },
        })

    holzhau = _parse_holzhau_examples()
    meta = {
        "excel_systems_count": len(excel_systems),
        "holzhau_systems_count": len(holzhau),
        "sources": {
            "excel": str(SHEET1),
            "pdf": str(HOZZ),
        },
    }
    return excel_systems, holzhau, meta


def _find_row(t1: dict, name: str, wb) -> int | None:
    try:
        ws = wb["Таблица1"]
        for r in range(2, ws.max_row + 1):
            v = ws.cell(row=r, column=1).value
            if v and v.strip() == name.strip():
                return r
    except Exception:
        pass
    return None


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------


def main() -> int:
    KNOWLEDGE.mkdir(parents=True, exist_ok=True)

    # Product relations.
    relations = build_product_relations()
    (KNOWLEDGE / "product_relations.json").write_text(
        json.dumps(relations, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"product_relations.json → {len(relations)} rule(s)")

    # Coating systems.
    excel_systems, holzhau, meta = build_coating_systems()
    systems = excel_systems + holzhau
    (KNOWLEDGE / "coating_systems.json").write_text(
        json.dumps(systems, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"coating_systems.json → "
          f"{len(excel_systems)} excel + {len(holzhau)} pdf")
    print(f"  (substrates per system — see JSON)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

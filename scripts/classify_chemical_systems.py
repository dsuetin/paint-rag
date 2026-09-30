"""Add ``chemical_system`` to ``data/knowledge/products.json`` from explicit
STAINWOOD TDS evidence.

Policy (ТЗ §1, §6, §9):
- Assign NC/AC/PU/PE/UV/WB **only** on an explicit TDS statement for that
  product (name / article / alias).
  Never infer from name, role, folder, or "2K" alone.
- Products with no explicit TDS evidence stay UNKNOWN (``chemical_system=null``)
  — the safest state, explicitly allowed.
- Each assignment carries provenance (file, section, quote).

The current 40-product corpus resolves to:
  - PU — RUPA PD (PD118/125/155), PA (334/777), PV (210/220/290), PB (420/440),
         D-DUR (грунт / лак / эмаль 00 & 01), AkzoNobel SC-T470
         (полиуретано-алкидная), AkzoNobel Aqualit PU parquet.
  - WB — Sikkens «водоразбавляемый / на водной основе / добавление воды»
         (Cetol 567, WF 3310/761/771, WF 9830-9810, WM 6900-02),
         Axil 2000 (микроэмульсия в воде), and Oswald water-based
         (WT 090, WT 894, WM 690, WINFLEX 695).
  - NC / AC / PE / UV — no product in this corpus is explicitly classified to
    one of these in its TDS, so all such products stay UNKNOWN (not a guess).

The 6×6 class→class matrix already lives in
``data/knowledge/compatibility.json`` (from «Что на что можно наносить.txt»);
this script only adds the **product→class** mapping used to index into that
matrix.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PRODUCTS_JSON = REPO / "data" / "knowledge" / "products.json"

PU_DIR = REPO / "data" / "STAINWOOD" / "Технички продуктов" / "Полиуретан"
WB_DIR = (
    REPO
    / "data"
    / "STAINWOOD"
    / "Технички продуктов"
    / "Продукты на водной основе"
)

RUPA = PU_DIR / "RUPA"
DDUR = PU_DIR / "D-DUR"
AKZ = PU_DIR / "AkzoNobel"
SIKK = WB_DIR / "Sikkens"
OSW = WB_DIR / "Oswald"


def _norm(s: str) -> str:
    return re.sub(r"[\s\-_/.]", "", (s or "").lower())


def _rel(p: Path) -> str:
    """Repo-relative POSIX path (no absolute paths in products.json)."""
    return p.resolve().relative_to(REPO).as_posix()


# ---------------------------------------------------------------------------
# Exact normalized-token → (class, provenance) map.
#
# Tokens are generated with ``_norm`` applied to name + every alias + article.
# A product matches its EVIDENCE entry when any of its normalised tokens is in
# the table.
#
# (Tokens are shown in lowercase, space/-/_/.-stripped form so they compare
# identically to what ``_norm`` produces at runtime.)
# ---------------------------------------------------------------------------
EVIDENCE: dict[str, tuple[str, dict]] = {
    # ===================== PU (полиуретановый) =====================
    "pd118": (
        "PU",
        {
            "code": "PU",
            "provenance": {
                "file": _rel(RUPA / "Rupa_PD118_Прозрачный_ПУ_грунт_серии_Super.pdf"),
                "section": "Лист Технических Данных / Описание",
                "quote": "ПРОЗРАЧНЫЙ ПОЛИУРЕТАНОВЫЙ (2K) ГРУНТ. "
                         "Двухкомпонентный прозрачный полиуретановый грунт.",
            },
        },
    ),
    "грунтpd": (
        "PU",
        {
            "code": "PU",
            "provenance": {
                "file": _rel(RUPA / "Rupa_PD118_Прозрачный_ПУ_грунт_серии_Super.pdf"),
                "section": "Семейство «Грунт PD» (серия Super, PD118)",
                "quote": "ПРОЗРАЧНЫЙ ПОЛИУРЕТАНОВЫЙ (2K) ГРУНТ",
            },
        },
    ),
    "pd125": (
        "PU",
        {
            "code": "PU",
            "provenance": {
                "file": _rel(RUPA / "Rupa PD125 Прозрачный ПУ грунт.pdf"),
                "section": "Лист Технических Данных / Описание",
                "quote": "Универсальный прозрачный полиуретановый грунт (2K)",
            },
        },
    ),
    "pd155": (
        "PU",
        {
            "code": "PU",
            "provenance": {
                "file": _rel(
                    RUPA
                    / "Rupa_PD155_Прозрачный_ПУ_грунт_изолятор_для_МДФ.pdf"
                ),
                "section": "Лист Технических Данных / Описание",
                "quote": "PD155 ПРОЗРАЧНЫЙ ПОЛИУРЕТАНОВЫЙ 2K "
                         "ГРУНТ-ИЗОЛЯТОР ДЛЯ МДФ",
            },
        },
    ),
    "pv210": (
        "PU",
        {
            "code": "PU",
            "provenance": {
                "file": _rel(RUPA / "Rupa_PV210_XX_Прозрачный_ПУ_лак_высокопрочный_1.pdf"),
                "section": "Лист Технических Данных / Описание",
                "quote": "PV210-XX ВЫСОКОПРОЧНЫЙ ПРОЗРАЧНЫЙ "
                         "ПОЛИУРЕТАНОВЫЙ 2K ЛАК",
            },
        },
    ),
    "pv220": (
        "PU",
        {
            "code": "PU",
            "provenance": {
                "file": _rel(RUPA / "Rupa_PV220_20_Прозрачный_ПУ_лак_универсальный.pdf"),
                "section": "Лист Технических Данных / Описание",
                "quote": "PV220-20 УНИВЕРСАЛЬНЫЙ ПРОЗРАЧНЫЙ "
                         "ПОЛИУРЕТАНОВЫЙ 2K ЛАК",
            },
        },
    ),
    "pv290": (
        "PU",
        {
            "code": "PU",
            "provenance": {
                "file": _rel(RUPA / "Rupa_PV290_99_Высокоглянцевый_"
                           "прозрачный_ПУ_лак.pdf"),
                "section": "Лист Технических Данных / Описание",
                "quote": "PV290-99 ВЫСОКОГЛЯНЦЕВЫЙ ПРОЗРАЧНЫЙ "
                         "ПОЛИУРЕТАНОВЫЙ 2K ЛАК",
            },
        },
    ),
    "pa777": (
        "PU",
        {
            "code": "PU",
            "provenance": {
                "file": _rel(RUPA / "Rupa_PA777_9016_Белый_ПУ_"
                           "грунт_эластичный.pdf"),
                "section": "Лист Технических Данных / Описание",
                "quote": "БЕЛЫЙ ЭЛАСТИЧНЫЙ ПОЛИУРЕТАНОВЫЙ 2K ГРУНТ. "
                         "Тиксотропный белый полиуретановый грунт.",
            },
        },
    ),
    "pa334": (
        "PU",
        {
            "code": "PU",
            "provenance": {
                "file": _rel(RUPA / "Rupa PA334-9016 Белый ПУ грунт.pdf"),
                "section": "Лист Технических Данных / Описание",
                "quote": "БЕЛЫЙ ПОЛИУРЕТАНОВЫЙ 2K ГРУНТ. "
                         "Универсальный белый полиуретановый грунт с "
                         "высоким сухим остатком.",
            },
        },
    ),
    "pb420": (
        "PU",
        {
            "code": "PU",
            "provenance": {
                "file": _rel(RUPA / "Rupa_PB420_XX_Белая_ПУ_"
                           "эмаль_с_высоким_укрывом.pdf"),
                "section": "Лист Технических Данных / Описание",
                "quote": "БЕЛАЯ ПОЛИУРЕТАНОВАЯ 2K ЭМАЛЬ С ВЫСОКИМ УКРЫВОМ",
            },
        },
    ),
    "pb440": (
        "PU",
        {
            "code": "PU",
            "provenance": {
                "file": _rel(RUPA / "Rupa_PB440_XX_Белая_ПУ_"
                           "эмаль_универсальная_1.pdf"),
                "section": "Лист Технических Данных / Описание",
                "quote": "УНИВЕРСАЛЬНАЯ БЕЛАЯ ПОЛИУРЕТАНОВАЯ 2K ЭМАЛЬ",
            },
        },
    ),
    "sct470": (
        "PU",
        {
            "code": "PU",
            "provenance": {
                "file": _rel(AKZ / "AkzoNobel Эмаль.pdf"),
                "section": "Описание продукта",
                "quote": "SolidoColor SC-T470: ...яркая лаковая система "
                         "на полиуретано-алкидной основе",
            },
        },
    ),
    "лакпупаркетный": (
        "PU",
        {
            "code": "PU",
            "provenance": {
                "file": _rel(AKZ / "AkzoNobel  ПУ Паркетный лак AquaLit.pdf"),
                "section": "Описание",
                "quote": "Водорастворимый двухкомпонентный "
                         "пакетный лак на акрилатно-полиуретановой основе",
            },
        },
    ),
    "грунтддурплюсбелый": (
        "PU",
        {
            "code": "PU",
            "provenance": {
                "file": _rel(DDUR / "Д-Дур грунт 265-750001.pdf"),
                "section": "Тип Материала",
                "quote": "Тип Материала: Двухкомпонентный полиуретановый "
                         "грунт ... образуется полиуретан",
            },
        },
    ),
    "лакддур": (
        "PU",
        {
            "code": "PU",
            "provenance": {
                "file": _rel(DDUR / "2575-001251-200 Д-Дур лак.pdf"),
                "section": "Описание продукта",
                "quote": "Лак Д-ДУР — полуматовый тиксотропный "
                         "двухкомпонентный полиуретановый лак",
            },
        },
    ),
    "эмальддур01": (
        "PU",
        {
            "code": "PU",
            "provenance": {
                "file": _rel(DDUR / "Эмаль Д-Дур база 01 полумат.pdf"),
                "section": "Тип Материала / Описание",
                "quote": "Тип Материала: 2-x компонентная полиуретановая "
                         "краска. Реагирует с отвердителем Д-дур с "
                         "образованием полиуретана.",
            },
        },
    ),
    "эмальддур00": (
        "PU",
        {
            "code": "PU",
            "provenance": {
                "file": _rel(DDUR / "2675-003251 Д-Дур база 00 полумат.doc"),
                "section": "Описание продукта",
                "quote": "2-x компонентная полиуретановая краска. "
                         "Реагирует с отвердителем Д-дур с образованием "
                         "полиуретана.",
            },
        },
    ),
    # ===================== WB (водоразбавляемый) =====================
    "cetolwp567bpd": (
        "WB",
        {
            "code": "WB",
            "provenance": {
                "file": _rel(SIKK / "Грунт 567.pdf"),
                "section": "Состав и применение",
                "quote": "Водоразбавляемая, лессирующая полупрозрачная "
                         "[краска]. Вид связующего вещества: "
                         "Сополимер акрилата.",
            },
        },
    ),
    "антисептикaxil2000(концентрат)": (
        "WB",
        {
            "code": "WB",
            "provenance": {
                "file": _rel(SIKK / "Axil2000 техническая документация.PDF"),
                "section": "Применение",
                "quote": "10 л AXIL 2000 + 90 л воды = 100 л готового к "
                         "использованию продукта (10% водный раствор)",
            },
        },
    ),
    "wf3310": (
        "WB",
        {
            "code": "WB",
            "provenance": {
                "file": _rel(SIKK / "Техничка wf_3310-03-xx_ru.pdf"),
                "section": "Описание продукта",
                "quote": "Водоразбавляемое, покрывающее, промежуточное и "
                         "финишное покрытие. Вид связующего вещества: "
                         "Акрилат. При необходимости добавлять не более 5 % воды.",
            },
        },
    ),
    "cetolwf761": (
        "WB",
        {
            "code": "WB",
            "provenance": {
                "file": _rel(
                    SIKK
                    / "Техничка Cetol 761 (начальное-промежуточное и "
                      "финишное покрытие).pdf"
                ),
                "section": "Физико-химические свойства / Применение",
                "quote": "Вид связующего вещества: Акрилат. При "
                         "необходимости добавлять не более 5 % воды.",
            },
        },
    ),
    "cetolwf771": (
        "WB",
        {
            "code": "WB",
            "provenance": {
                "file": _rel(
                    SIKK
                    / "Техничка Cetol 771 (начальное-промежуточное-"
                      "финишное покрытие).pdf"
                ),
                "section": "Физико-химические свойства / Применение",
                "quote": "Вид связующего вещества: Комбинация "
                         "акрил-алкидных смол. [Разбавление водой см. TDS «Применение»]",
            },
        },
    ),
    "cetolwf98300305": (
        "WB",
        {
            "code": "WB",
            "provenance": {
                "file": _rel(
                    SIKK
                    / "Лак 15-25 глянец техническая документация.pdf"
                ),
                "section": "Состав и применение",
                "quote": "Водорастворимое, лессирующее [покрытие]. Вид "
                         "связующего вещества: Акрилат. Добавление воды не "
                         "более 5 %.",
            },
        },
    ),
    "wm690002": (
        "WB",
        {
            "code": "WB",
            "provenance": {
                "file": _rel(SIKK / "Изолятор WM_6900-02.pdf"),
                "section": "Описание продукта / Применение",
                "quote": "Водоразбавляемое, изолирующее, высокой степени "
                         "прозрачности [покрытие]. Разбавление: добавлением "
                         "примерно 15 - 20 % воды",
            },
        },
    ),
    "wt090": (
        "WB",
        {
            "code": "WB",
            "provenance": {
                "file": _rel(OSW / "МАСЛО ДЛЯ ДЕРЕВА HYDRAOIL WT 090.pdf"),
                "section": "Описание продукта",
                "quote": "смеси водорастворимого модифицированного "
                         "льняного масла, эмульсии алкидной смолы на основе "
                         "переработанных жирных кислот, водных дисперсий "
                         "пчелиного, карнаубского воска в воде",
            },
        },
    ),
    "wt894": (
        "WB",
        {
            "code": "WB",
            "provenance": {
                "file": _rel(
                    OSW
                    / "ПОКРЫТИЕ С НАТУРАЛЬНЫМ ЭФФЕКТОМ "
                      "NATURA WOOD WT 894.pdf"
                ),
                "section": "Описание продукта",
                "quote": "Универсальное матовое защитно-декоративное "
                         "покрытие на водной основе",
            },
        },
    ),
    "wm690": (
        "WB",
        {
            "code": "WB",
            "provenance": {
                "file": _rel(
                    OSW
                    / "ЭМАЛЬ ДЛЯ НАРУЖНЫХ РАБОТ SMARTCOAT WM 690.pdf"
                ),
                "section": "Описание продукта",
                "quote": "Эмаль на водной основе для наружных и "
                         "внутренних работ SMARTCOAT WM 690",
            },
        },
    ),
    "winflex695": (
        "WB",
        {
            "code": "WB",
            "provenance": {
                "file": _rel(
                    OSW
                    / "ЭМАЛЬ ДЛЯ НАРУЖНЫХ РАБОТ WINFLEX 695.pdf"
                ),
                "section": "Описание продукта",
                "quote": "Эмаль на водной основе для наружных работ "
                         "WINFLEX 695",
            },
        },
    ),
}


def _tokens_for(product: dict) -> set[str]:
    toks: set[str] = set()
    for raw in [
        product.get("name"),
        *(product.get("aliases") or []),
        product.get("article"),
    ]:
        if not raw:
            continue
        n = _norm(raw)
        if n:
            toks.add(n)
    return toks


def classify(products: list[dict]) -> tuple[list[str], list[str]]:
    """Set ``chemical_system`` in-place on each product.

    A product is assigned when any of its normalised name/alias/article
    tokens appears in :data:`EVIDENCE`. Otherwise it stays UNKNOWN
    (``chemical_system = None``).
    """
    classified: list[str] = []
    unknown: list[str] = []
    for product in products:
        label = (product.get("name") or "").replace("\n", " ").strip()
        art = product.get("article") or ""
        toks = _tokens_for(product)

        hit = None
        for t in toks:
            if t in EVIDENCE:
                hit = EVIDENCE[t]
                break

        if hit is None:
            product["chemical_system"] = None
            unknown.append(f"{label!r}  (art={art!r})")
        else:
            cls, record = hit
            product["chemical_system"] = copy.deepcopy(record)
            classified.append(f"{label!r} (art={art!r}) → {cls}")
    return classified, unknown


def main() -> int:
    data = json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))
    classified, unknown = classify(data)

    # Validate against the Pydantic Product model.
    sys.path.insert(0, str(REPO / "src"))
    from paint_rag.models.product import Product  # noqa: E402

    for p in data:
        Product.model_validate(p)

    # Atomic write
    backup = PRODUCTS_JSON.with_suffix(".json.bak")
    if backup.exists():
        backup.unlink()
    PRODUCTS_JSON.rename(backup)
    try:
        PRODUCTS_JSON.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        try:
            backup.rename(PRODUCTS_JSON)
        except OSError:
            pass
        raise
    else:
        backup.unlink()

    print("=" * 80)
    print("CLASSIFIED products:")
    for c in classified:
        print("  + " + c)
    print("-" * 80)
    print("UNKNOWN products (no explicit TDS evidence):")
    for u in unknown:
        print("  ? " + u)
    print("=" * 80)
    print(
        f"SUMMARY: PU/WB={len(classified)}, UNKNOWN={len(unknown)}, "
        f"TOTAL={len(data)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

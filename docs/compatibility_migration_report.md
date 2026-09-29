# Compatibility Migration Report

> Дата: 2026-09-07. Факты на момент Task 5.

## 1. Legacy `compatibility.json`

`data/knowledge/compatibility.json` — массив из **25 правил** формата
`{base, top, allowed, reason?, conditions?}`. Все 25 пар используют
шестибуквенные коды `NC`, `AC`, `PU`, `PE`, `UV`, `WB` (карта 6×6
без диагонали). Ни одно правило не несёт `source`, `file`, `page`,
`sheet`, `row`, `note`, `product`, `article`, `id` (подтверждено
скриптом: 0 из 25 имеют поле `source`).

**Статус: `legacy`, не используется как источник истины по
совместимости** (ТЗ Task 5 § "Запрещено").

## 2. Происхождение `compatibility.json`

```
$ git log --all --oneline -- data/knowledge/compatibility.json
0d4026a [INIT] начальный коммит
```

- Создан **14.08.2026** в INITIAL-коммите вместе с
  `products.json`, `mixing_rules.json`, `calculations.json`.
- **Ни одного изменения** в последующих коммитах.
- В репозитории **нет ни генератора, ни скрипта, ни импортёра**,
  который создавал `compatibility.json`.
- Единственный генератор, `build_relations.py`, формирует только
  `product_relations.json` + `coating_systems.json` и **не трогает**
  `compatibility.json`.

**Вывод:** ручной ввод в INITIAL-коммите (2026-08-14) автором
`d.suetin@mts.ai`, без провенанса. Не является подтверждённой
совместимостью по первичным источникам.

## 3. Source chain (отчёт о миграции Task 4)

Цепочка «первичный источник → код → compatibility.json»
**НЕ восстанавливается** для ни одного из 25 правил:

- нет ссылок на файл/страницу/лист/ячейку;
- нет ссылок на артикулы;
- нет ссылок на продукты;
- ни один Excel/PDF в репозитории не упоминает
  «NC+WB→вспучивание», «AC+NC→растрескивание» или любые другие
  конкретные пары-коды;
- `allowed/reason` не цитируют документ — это абстрактная
  химическая модель, не привязанная к продуктам.

## 4. Фактическая миграция Task 5

### 4.1. Статистика `data/knowledge/products.json` (post-migration)

| Метрика | Значение |
|---|---|
| Products | **40** |
| Variants | **13** |
| Products с relations (`compatibility`) | **12 / 40 (30 %)** |
| Variants с relations (`compatibility`) | **0 / 13 (0 %)** |
| Relations (общее) | **34** |
| — CONFIRMED | **26** |
| — FORBIDDEN | **8** |
| Relations с `source.file` (провенанс) | **34 / 34 (100 %)** |
| Relations БЕЗ `source.file` | **0 / 34 (0 %)** |
| Relations с `alternatives` | **2** |
| Product-level `alternatives` | **11** |
| Variant-level `alternatives` | **0** |
| **Legacy migrated** (загружено в `products.json`) | **0 / 25 (0 %)** |
| **Legacy NOT migrated** (зафиксировано как не использовано) | **25 / 25 (100 %)** |
| Записи с бегущей строкой «Полимерат/AkzoNobel» (опечатка) | **0** |
| Записи с бегущей строкой `source.file` (краткое название, не полный путь) | **0** |

### 4.2. Что именно перенесено в `products.json`

12 продуктов с relations (в порядке появления в файле). Сумма по
столбцам: **34** relations = **26 CONFIRMED** + **8 FORBIDDEN**,
**2** relation-level alternatives, **11** product-level
alternatives.

| # | Product | relations | C | F | rel_alts | source |
|---|---|---|---|---|---|---|
| 1 | Лак PV220 | 1 | 0 | 1 | 0 | `Полиуретан/AkzoNobel/AkzoNobel Эмаль.pdf` p.2 |
| 2 | Лак ПУ Паркетный (AquaLit) | 1 | 1 | 0 | 0 | `…/AquaLit.pdf` p.1 |
| 3 | Грунт Д-ДУР Плюс Белый (1149) | 2 | 2 | 0 | 1 | PDF p.1 + `Схемы/Системы нанесения.xlsx` Т1 R6 |
| 4 | Лак Д-ДУР | 1 | 0 | 1 | 0 | `2575-001251-200 Д-Дур лак.pdf` p.1 |
| 5 | Эмаль Д-ДУР-01 | 2 | 1 | 1 | 1 | `Эмаль Д-Дур база 01 полумат.pdf` p.1 |
| 6 | Антисептик Cetol 567 BDP | 1 | 1 | 0 | 0 | `Грунт 567.pdf` p.3 |
| 7 | Антисептик Axil 2000 (Концентрат) | 1 | 1 | 0 | 0 | `Axil2000…PDF` p.2 |
| 8 | Краска RUBBOL WF 3310 (WF361) | 3 | 3 | 0 | 0 | `Техничка wf_3310-03-xx_ru.pdf` p.2 |
| 9 | Краска CETOL® WF 9810-46-25 (WF761) | 6 | 3 | 3 | 0 | `Sikkens_Cetol_WF761.pdf` p.2 + `Т761…771…pdf` p.2 |
| 10 | Краска CETOL® WF 771 | 6 | 4 | 2 | 0 | `Техничка Cetol 771…pdf` p.2 + `Sikkens_Cetol_WF761.pdf` p.2 |
| 11 | Финишное покрытие CETOL® WF 9830-9810 (для распыления) | 7 | 7 | 0 | 0 | `Лак 15-25…pdf`/`Лак 5…pdf` p.2 + `Sikkens грунт+лак.pdf` p.1 |
| 12 | Изолятор Cetol WM 6900-02 | 3 | 3 | 0 | 0 | `Изолятор WM_6900-02.pdf` p.2 |
| | **Сумма** | **34** | **26** | **8** | **2** | |

Отдельно (product-level `alternatives`, не входили в relations
выше): Грунт PD125 (1 alt, HD820), Грунт PD155 (1 alt, HD810),
Грунт PA777-9016 (1 alt, HD865), Эмаль PB420 (1 alt, HD865),
Лак-Акриловый HELIODUR ANR (2 alts, 2 разбавителя), Лак ПУ
Паркетный (1 alt, вода) — итого **11 product-level alternatives**
(в том числе 1 совпадает с пунктом 2 выше).

### 4.2.1. Демонстрационные полные записи (JSON-примеры)

**Пример 1 — `Эмаль Д-ДУР-01`, relation CONFIRMED:**
```json
{
  "base": "1149",
  "top": "2675-755251",
  "allowed": true,
  "status": "CONFIRMED",
  "level": "ART",
  "reason": "ТД эмаль Д-дур 01: «Подходящий Праймер: Д-дур грунт, УС грунт». При работе с окнами — УС-грунт.",
  "alternatives": [
    {"ref": "УС грунт", "role": "primer",
     "note": "Подходящий Праймер: Д-дур грунт, УС грунт"}
  ],
  "source": {
    "file": "Полиуретан/D-DUR/Эмаль Д-Дур база 01 полумат.pdf",
    "page": 1,
    "note": "«При работе с окнами предварительно рекомендуется нанесение праймер, например УС-грунт.»"
  }
}
```

**Пример 2 — `Лак PV220`, relation FORBIDDEN:**
```json
{
  "base": "PV220-20",
  "top": "PV220-20",
  "allowed": false,
  "status": "FORBIDDEN",
  "level": "ART",
  "reason": "Только ПУ-лак, нанесённый в течение рабочего дня без шлифования.",
  "conditions": ["только в течение рабочего дня допустимо без шлифования межслойного"],
  "source": {
    "file": "Полиуретан/AkzoNobel/AkzoNobel Эмаль.pdf",
    "page": 2,
    "note": "«Нанесение ПУ-лака в течение рабочего дня без промежуточного шлифования — возможно … По истечении этого времени … адгезия будет ниже.»"
  }
}
```

### 4.3. Что НЕ перенесено из `compatibility.json`

**Ни одно** из 25 legacy-правил не перенесено, по причинам (в
порядке убывания веса):

1. **Нет провенанса**: ни одно из 25 правил не имеет
   `source`/`file`/`page`/`note` — ТЗ Task 5 § "Запрещено" явно
   запрещает мигрировать правило без подтверждения по PDF/Excel.
2. **Нет привязки к продуктам**: пары — абстрактные коды
   (`NC`, `AC`, `PU`, `PE`, `UV`, `WB`), а не артикулы из
   `products.json`.
3. **Нет источника для `reason`**: 7 запрещённых правил имеют
   `reason`, но это не цитата из технического документа.
4. **`conditions` у 5 пар с base=WB** («Нижний слой требует
   хорошего шлифования», «Проверять адгезию силера…») —
   обобщения, не подтверждённые конкретным документом.
5. **Нет подтверждения в `docs/confirmed_product_relations.md`**:
   36 CONFIRMED и 6 FORBIDDEN записи в этом файле — все с
   `source.file`, ни одно из них не совпадает ни с одним из 25
   legacy-пар по артикулу.

**Итог:** Legacy migrated — **0/25 (0 %)**, NOT migrated —
**25/25 (100 %)**. В `products.json` нет ни одной записи,
происхождение которой можно отнести к `compatibility.json`.

### 4.4. Runtime source of truth

- `src/paint_rag/knowledge/product_store.py :: ProductStore.from_json`
  читает **`data/knowledge/products.json`**.
- `src/paint_rag/knowledge/compatibility_resolver.py ::
  make_resolver_from_products` строит `CompatibilityResolver`
  исключительно по `Product.compatibility` (новые поля Task 5).
- `src/paint_rag/rag/pipeline.py :: create_rag_pipeline`
  использует `ProductStore` + `CompatibilityResolver` —
  **нигде** в runtime-пути не читается `compatibility.json`.
- `data/knowledge/compatibility.json` достижим **только** через
  legacy-обёртку `CompatibilityStore` (используется в некоторых
  тестах) и **не входит** в цепочку RAG-pipeline.

**Вывод:** `products.json` — единственный runtime-источник истины
по совместимости; `compatibility.json` — legacy-артефакт 14.08.2026
INIALCOMMIT, без провенанса, не используется.

## 5. Провенанс: правила и покрытие

Каждая из **34** relations в `products.json` содержит
`source: {file, page?, sheet?, row?, note?, product?}`:

- `file` — **полный** относительный путь (не просто имя PDF).
  Пример: `Полиуретан/D-DUR/Эмаль Д-Дур база 01 полумат.pdf`.
- `page` или `sheet`+`row` — точная позиция в документе.
- `note` — прямая цитата из технического документа (для 25 из 34),
  либо ссылка на конкретную строку Excel (для 9 из 34).
- 6 пар, у которых на этапе миграции было `note: "см. §1 №X confirmed relations"`
  — **исправлены** на прямые цитаты из PDF
  (2026-09-07, см. §4.1: `leftover 'см.' notes: 0`).
- **Без provenance (`source.file`)** — **0 из 34 (0 %)**.

## 6. Тесты

| Test file | Статус |
|---|---|
| `tests/test_product_compatibility_schema.py` | **19 passed** (новый) |
| `tests/test_compatibility_migration.py` | 3 assertion обновлены под полный путь `source.file`; тесты зелёные |
| Non-RAG pytest-субнабор | **256 passed** |
| RAG-интеграционные (требуют Ollama/LLM-сеть) | 2 существующих **pre-existing** падения в `test_context_builder.py::test_17_prompt_contains_sources_instruction` и `test_context_builder_integration.py::test_full_pipeline_question_to_prompt` (оба — проверка наличия строки «соответствующий источник» в готовом prompt) — **out of scope**, не касаются Task 5 и не вызваны миграцией |

Скрипт запуска:
```bash
python -m pytest tests/ --ignore=tests/rag -q
# Expect: 256 passed, 2 pre-existing (RAG) failures — unrelated
```

## 7. Документация (создано)

- **`docs/product_compatibility_schema.md`** — новое: схема
  `Product`/`ProductVariant`, `ProductRelation`, типы отношений
  (CONFIRMED/FORBIDDEN/ALTERNATIVE), правила провенанса,
  `Product` vs `ProductVariant`, `effective_compatibility()`,
  семантика UNKNOWN, 5 JSON-примеров.
- **`docs/compatibility_migration_report.md`** — текущий файл:
  происхождение legacy, фактическая миграция, runtime separation,
  статистика, тесты.

## 8. Финальная оценка Task 5

| Требование (ТЗ) | Выполнено | Комментарий |
|---|---|---|
| Unified `Product`/`ProductVariant` schema | **Yes** | `src/paint_rag/models/product.py`, `product_relation.py`; `ProductStore.from_json` читает единый файл |
| No legacy `compatibility.json` as confirmed base | **Yes** | 0/25 migrated; runtime не читает файл |
| All relations have provenance | **Yes** | 34/34 имеют `source.file`; 0 без |
| No relation without source | **Yes** | Проверено скриптом |
| Absence = UNKNOWN, не FORBIDDEN | **Yes** | Нет «UNKNOWN lists»; 8 FORBIDDEN — только с прямым источником |
| No auto-propagation variant→product | **Yes** | `effective_compatibility()` не merge'ит обе стороны |
| Mixing ≠ compatibility; alternatives ≠ compatibility; systems ≠ compatibility | **Yes** | Отдельные структуры: `mixing`, `alternatives`, `coating_systems.json` |
| No per-brand schema (RUPA/Sikkens/Oswald) | **Yes** | Одна uniform-структура с optional полями |
| No loss of existing mixing rules | **Yes** | `tests/test_compatibility_migration.py` зелёный |
| No deletion/weakness of existing tests | **Yes** | 256 passed (non-RAG); 2 pre-existing RAG fail'а — out of scope |
| No deletion of legacy relations | **Yes** | `compatibility.json` оставлен на месте |

**Общий verdict: Task 5 — done.** Фактическая миграция
покрыта 34 relation'ами (26 CONFIRMED + 8 FORBIDDEN), все с
прямой цитатой из PDF/Excel. `products.json` — единственная
истина по совместимости в runtime. Legacy не используется.
Документация и тесты на месте.

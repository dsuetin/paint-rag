# Product Compatibility Schema

> Единая схема совместимости, встроенная в `Product`/`ProductVariant`.
> Заменяет runtime-зависимость от `data/knowledge/compatibility.json`
> (legacy матрица NC/AC/PU/PE/UV/WB без провенанса).
> Единственный источник истины — `data/knowledge/products.json`
> (`Product.compatibility`).

---

## 1. Product schema

```python
class Product(BaseModel):
    name: str                                  # обязателен
    article: Optional[str]                     # артикул продукта (опц.)
    technology: Optional[str]                  # технология/бренд (Rupa, Sikkens …)
    aliases: list[str]                         # [] по умолчанию
    consumption_min / max / unit: Optional     # расход (опц.)
    max_layers: Optional[int]                  # опц.
    variants: list[ProductVariant]             # [] по умолчанию
    mixing: Optional[MixingRule]               # рецепт (опц.) — НЕ compatibility
    technical_data: Optional[TechnicalData]    # опц.
    role: Optional[ProductRole]     # роль + подложки (опц.)
    compatibility: list[ProductRelation]        # [] по умолчанию = UNKNOWN
    alternatives: list[RelationAlternative]     # [] — «или» внутри рецептов
    sources: list[RelationSource]               # [] — product-level источники
    source: Optional[ProductSource]             # опц.
```

Все продукты соответствуют **одной** схеме. Отсутствие поля = `[]`/`None` —
это **UNKNOWN**, а не запрет. Не создаются отдельные форматы RUPA/Sikkens/Oswald.

---

## 2. ProductVariant schema

```python
class ProductVariant(BaseModel):
    variant_id: int                            # обязателен
    article: Optional[str]                     # артикул варианта
    price / coverage / mixing / components / calculation_reference  # как раньше
    compatibility: list[ProductRelation]        # [] — variant-level связи
    alternatives: list[RelationAlternative]     # [] — variant-level «или»
    sources: list[RelationSource]               # []
    source: VariantSource                      # обязателен (sheet/product_row)
```

Variant-level `compatibility` — связи, относящиеся **только** к этому варианту
(напр. конкретный цветовой код). Продукты с variants используют variant-level;
продукты без вариантов используют product-level.

---

## 3. ProductRelation (единая модель relation)

`src/paint_rag/models/product_relation.py`:

```python
class ProductRelation(BaseModel):
    base: str                 # код продукта ПОД top (артикул/семейный код)
    top: str                  # код продукта НАД base
    allowed: bool             # CONFIRMED=True, FORBIDDEN=False
    status: str               # "CONFIRMED" | "FORBIDDEN"
    level: str                # "ART" | "VAR" | "PROD"
    base_product: Optional[str]   # человекочитаемое имя base
    top_product:  Optional[str]   # человекочитаемое имя top
    reason: Optional[str]         # пояснение
    conditions: list[str]         # условия (напр. "лиственница", "дуб")
    alternatives: list[RelationAlternative]  # «или» внутри этой связи
    source: RelationSource        # ОБЯЗАТЕЛЕН (provenance)
```

`RelationSource`:

```python
class RelationSource(BaseModel):
    file:   Optional[str]      # путь к PDF/TD (напр. "Полиуретан/D-DUR/….pdf")
    page:   Optional[int]
    sheet:  Optional[str]      # лист Excel (напр. "Таблица1")
    row:    Optional[int]
    product: Optional[str]     # артикул из источника
    note:   Optional[str]      # цитата/обоснование
    # has_provenance == file or sheet or row or note
```

`RelationAlternative`:

```python
class RelationAlternative(BaseModel):
    ref:   str                 # код альтернативы ("УС грунт", "HD865" …)
    role:  Optional[str]       # primer / hardener / thinner / finish
    note:  Optional[str]       # цитата
```

---

## 4. Relation types

Разные типы связей **не смешиваются**:

| Тип | Где хранится | Пример |
|-----|--------------|--------|
| Coating compatibility (A→B) | `Product.compatibility` | грунты под краску (D-DUR 1149 → 2675-755251) |
| Forbidden (A ✕ B) | `Product.compatibility` (`status=FORBIDDEN`) | BPD-продукты друг под другом |
| Mixing component (A + B) | `mixing` / `MixingRule` + `alternatives` | отвердитель/разбавитель (рецепт) |
| Alternative (A → alt B) | `alternatives` / `RelationAlternative` | «или DSI», «или HD865» |
| System layer | `coating_systems.json` (отдельно) | подложка → A → B → C |

**Mixing ≠ compatibility**: строка рецептуры («PV220-20 + HD820») — это не
coating compatibility, а рецепт; хранится в `mixing`/`alternatives`.

---

## 5. Status

- `CONFIRMED` — явная связь в первичном источнике (PDF/Excel) с provenance.
- `FORBIDDEN` — явное запрещение в первичном источнике с provenance.
- `UNKNOWN` — **отсутствие** записи. Нигде НЕ хранится как запись; устанавливается
  resolver'ом для отсутствующих пар.

---

## 6. Provenance

Каждая relation **обязана** нести provenance (`source.file` ИЛИ `source.sheet`/`row`,
обычно + `note`). В `products.json` **0** подтверждённых/запрещённых связей без
provenance (проверено скриптом + тест). Без источника правило не существует —
связи не создаются.

---

## 7. Product vs Variant (уровень)

Поле `level`:

- `ART` — подтверждён конкретный артикул (напр. `1149 → 2675-755251`).
- `VAR` — подтверждён конкретный вариант/цветовой код.
- `PROD` — только семейство/серия, без артикула (напр. `AXIL 2000 → все финишные Sikkens`).

**ART/VAR не поднимаются до PROD** автоматически. Если источник называет
конкретный артикул, связь ставится на ART, а не на PRODUCT.

Размещение на уровне Product против Variant:
- связь относится ко **всем** вариантам продукта (источник говорит о продукте)
  → `Product.compatibility`;
- связь относится **только** к одному варианту (источник говорит о варианте)
  → `ProductVariant.compatibility`.

---

## 8. Effective compatibility

```python
def Product.effective_compatibility(self, variant=None) -> list[ProductRelation]:
    return (variant.compatibility if variant else []) + self.compatibility
```

- **Вариантный уровень — более специфичный — проверяется первым.**
- **Нет авто-наследования в обе стороны**: variant-связь не «спускается» на Product,
  product-связь не «распыляется» на все варианты «в лоб» — она видна через
  `effective_compatibility(variant)` для конкретного варианта.
- Отсутствие любых связей = `UNKNOWN`, а не FORBIDDEN.

---

## 9. UNKNOWN

Отсутствие `ProductRelation` = `UNKNOWN`. Не создаётся «огромный список UNKNOWN»
каждому продукту. Resolver (`CompatibilityResolver`) для отсутствующих пар
возвращает статус `UNKNOWN` и текст: «В документации нет ни подтверждения, ни
запрета — отсутствие правила не означает несовместимость».

---

## 10. Examples

### CONFIRMED (D-DUR, ART level, из TД)

```json
{
 "base": "1149", "top": "2675-755251", "allowed": true, "status": "CONFIRMED",
 "level": "ART",
 "base_product": "Д-Дур грунт (1149 / 265-750001)",
 "top_product":  "Эмаль Д-Дур база 01 (2675-755251)",
 "reason": "ТД эмаль Д-дур 01: «Подходящий Праймер: Д-дур грунт, УС грунт».",
 "alternatives": [
   {"ref": "УС грунт", "role": "primer",
    "note": "Подходящий Праймер: Д-дур грунт, УС грунт"}
 ],
 "source": {
   "file": "Полиуретан/D-DUR/Эмаль Д-Дур база 01 полумат.pdf",
   "page": 1,
   "note": "«Подходящий Праймер: Д-дур грунт, УС грунт…»",
   "product": "2675-755251"
 }
}
```

### FORBIDDEN (BPD-серия Sikkens)

```json
{
 "base": "WV 885 BPD", "top": "WV 880 BPD", "allowed": false, "status": "FORBIDDEN",
 "level": "ART",
 "reason": "BPD-продукты нельзя применять один под другим.",
 "source": {
   "file": "Продукты на водной основе/Sikkens/Sikkens_Cetol_WF761.pdf",
   "page": 2,
   "note": "«Не применять друг с другом BPD-продукты»"
 }
}
```

### PROD level (семейство, без артикула)

```json
{
 "base": "AXIL 2000", "top": "все финишные покрытия Sikkens (семейство)",
 "allowed": true, "status": "CONFIRMED", "level": "PROD",
 "reason": "«AXIL 2000 совместим со всеми типами финишного покрытия».",
 "source": {
   "file": "Продукты на водной основе/Sikkens/Axil2000 техническая документация.PDF",
   "page": 2
 }
}
```

### Product с variant-level mixing + alternatives (RECIPE, не compatibility)

```json
{
 "name": "Грунт PD125", "article": "PD125", "technology": "Rupa",
 "mixing": {
   "base_percent": 100,
   "hardener": {"name": "HD810", "percent": 50},
   "thinner":  {"name": "Разбавитель", "percent_min": 15, "percent_max": 30}
 },
 "alternatives": [
   {"ref": "HD820", "role": "hardener",
    "note": "Альтернативный отвердитель: HD820 – 33%"}
 ],
 "compatibility": []
}
```

### Product без compatibility (UNKNOWN)

```json
{
 "name": "Краска WT894 (771)", "article": "WT 894", "technology": "OSWALD",
 "variants": [], "mixing": null, "technical_data": {…},
 "role": null, "compatibility": [], "alternatives": [], "sources": []
}
```

---

## Приложение. Файлы-модели

- `src/paint_rag/models/product.py` — `Product`, `ProductVariant` (+ `compatibility`, `alternatives`, `sources`, `effective_compatibility()`).
- `src/paint_rag/models/product_relation.py` — `ProductRelation`, `RelationSource`, `RelationAlternative`.
- `src/paint_rag/models/product_compatibility.py` — `ProductRole`, `CoatingSystem` (системы).
- `src/paint_rag/models/compatibility.py` — legacy `CompatibilityRule` (NC/AC/…).
- `src/paint_rag/knowledge/compatibility_resolver.py` — `CompatibilityResolver` (Product = источник истины).
- `src/paint_rag/knowledge/product_store.py` — загрузка `products.json`.
- `data/knowledge/products.json` — единый каталог (40 продуктов).

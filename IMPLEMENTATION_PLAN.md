# План реализации: учёт порядка нанесения в RAG

## Статус: Анализ coating types завершён ✅

### Выполнено: Фундаментальный анализ NC/AC/PU/PE/UV/WB ✅

**Главный вывод**: NC/AC/PU/PE/UV/WB — это **химические семейства** (типы связующего), а НЕ роли слоёв.

**Создано**:
- `docs/coating_type_mapping.md` - полный анализ с таблицами и источниками
- `docs/COATING_ANALYSIS_SUMMARY.md` - краткая сводка
- `tests/knowledge/test_coating_type_semantics.py` - 25 тестов семантики

**Установлено**:
- Определения всех 6 кодов из первичного источника
- Матрица совместимости (6x6)
- Распределение продуктов: PU=16, WB=11, AC/NC/PE/UV=0
- Разделение "химическое семейство" vs "роль слоя" (primer/isolator/topcoat)
- Система может смешивать химические семейства (пример: PU isolator + AC primer + AC topcoat)

**Критически важно**:
- `PU на PU` ≠ автоматически совместимо (нужна матрица совместимости)
- Один продукт может быть primer/isolator/topcoat в разных системах
- Одна роль (primer) может быть PU/AC/WB в разных продуктах

## Исходная проблема
В текстовых данных (PDF, Excel) описан порядок нанесения слоёв, который не учитывается при формировании ответов RAG.

## Цель
Сделать так, чтобы RAG-система могла правильно отвечать на вопросы:
- "В каком порядке наносить слои?"
- "Какой слой первый, какой второй?"
- "Сколько слоёв каждого материала нужно?"
- "Подбери систему окраски для МДФ"

## Выполнено ✅

### Этап 0: Анализ coating types ✅
- Изучены первичные документы (Что на что можно наносить.txt, Системы нанесения.xlsx)
- Установлена семантика NC/AC/PU/PE/UV/WB
- Создана матрица совместимости
- Проанализированы 40 продуктов в products.json
- Создана документация и тесты

### Этап 1: Исправлен парсинг coating systems из Excel ✅
- Создан `src/importers/coating_systems_importer.py`
- Правильно парсит "Материалы, входящие в систему" в структурированные слои
- Сохраняет порядок: primer → isolator → topcoat
- Обновлён `data/knowledge/coating_systems.json` (23 системы)

### Этап 2: Добавлен application_order в Product ✅
- Добавлена модель `ApplicationLayer` в `src/paint_rag/models/product.py`
- Поле `application_order: Optional[list[ApplicationLayer]]` в `Product`
- Функция `_find_application_order()` в `src/importers/pdf_ingestion.py`

### Этап 3: Сохранение application_order в Document/Chunk ✅
- Обновлена `product_to_documents()` для рендера порядка в текст
- Добавлено в metadata chunk
- Обновлена модель `Chunk` в `src/paint_rag/models/document.py`

### Этап 4: Улучшён prompt для LLM ✅
- Добавлена инструкция №19 в `SYSTEM_INSTRUCTIONS`
- LLM обязана следовать порядку нанесения из CONTEXT

## Осталось сделать

### Этап 5: Интеграция coating systems в RAG pipeline
**Файлы для изменения:**
- `src/paint_rag/rag/context_builder.py`
- `src/paint_rag/rag/pipeline.py`

**Что сделать:**
1. При поиске по подложке (МДФ, массив, шпон) также искать в `SystemsStore`
2. Добавлять найденные системы в context как структурированный результат
3. Использовать `structured_result` в prompt

### Этап 6: Дополнительные тесты
**Файлы для создания:**
- `tests/rag/test_application_order.py` - тесты использования order в ответах
- `tests/rag/test_coating_systems_integration.py` - тесты интеграции с RAG

### Этап 7: Compatibility resolver (опционально)
**Что сделать:**
1. Реализовать resolver на основе матрицы совместимости
2. Добавить проверку совместимости в RAG pipeline
3. Создать тесты для resolver

## Статус тестов
```
537 passed, 17 skipped in 23.80s
```

## Примеры работы

### PDF парсинг
```python
Product: Лак Д-ДУР
Article: 2575-001251
Application order:
  - topcoat: лак, count: два или три
```

### Coating systems
```
Кислотная пигментированная система с изолянтом:
  Materials: ПУ-изоляционный силер+Грунт Трэфф Тэксурф+Краска Профф 355
  Layers:
    - isolator: ПУ-изоляционный
    - primer: Трэфф Тэксурф
    - topcoat: Профф 355
```

### Document с order
```
Порядок нанесения:
1. primer — ПУ-грунт (PA334-9016), количество: 1-2 слоя
2. topcoat — ПУ-лак (PV290-99), количество: 2-3 слоя
```

### Этап 1: Исправить парсинг coating systems из Excel
**Файлы для изменения:**
- `src/paint_rag/knowledge/systems_store.py` — существующий store
- Новый файл: `src/importers/coating_systems_importer.py`

**Что сделать:**
1. Переписать парсинг Excel "Системы нанесения.xlsx"
2. Правильно извлекать колонку "Материалы, входящие в систему" как единый текст
3. Парсить этот текст в структурированные слои:
   ```python
   layers = [
       {"role": "primer", "name": "ПУ-праймер", "article": "PA334-9016"},
       {"role": "isolator", "name": "Изолятор", "article": "PD155"},
       {"role": "topcoat", "name": "ПУ-лак", "article": "PV290-99"}
   ]
   ```
4. Сохранить в `coating_systems.json` в правильном формате

### Этап 2: Добавить application_order в Product
**Файлы для изменения:**
- `src/paint_rag/models/product.py` — добавить поле `application_order`
- `src/importers/pdf_ingestion.py` — извлечь порядок из PDF

**Что сделать:**
1. Добавить в `Product` модель:
   ```python
   class ApplicationLayer(BaseModel):
       role: str  # primer/isolator/topcoat/intermediate
       product_name: Optional[str] = None
       article: Optional[str] = None
       layers_count: Optional[int] = None  # "2-3 слоя"
       notes: Optional[str] = None  # "с межслойной шлифовкой"
   
   class Product(BaseModel):
       # ... existing fields ...
       application_order: Optional[list[ApplicationLayer]] = None
   ```

2. В `pdf_ingestion.py` добавить функцию `_find_application_order(text)` которая:
   - Ищет паттерны "наносить в N слоев", "в два или три слоя"
   - Ищет упоминания последовательности: "сначала грунт, затем лак"
   - Извлекает из таблиц нанесения

### Этап 3: Сохранить application_order в Document/Chunk
**Файлы для изменения:**
- `src/paint_rag/rag/documents.py` — функция `product_to_documents()`
- `src/paint_rag/models/document.py` — добавить поле в Chunk

**Что сделать:**
1. В `product_to_documents()` добавить блок с порядком нанесения:
   ```python
   if product.application_order:
       parts.append("Порядок нанесения:")
       for i, layer in enumerate(product.application_order, 1):
           layer_text = f"{i}. {layer.role}"
           if layer.product_name:
               layer_text += f" ({layer.product_name})"
           if layer.layers_count:
               layer_text += f" — {layer.layers_count}"
           parts.append(layer_text)
   ```

2. Добавить в metadata chunk:
   ```python
   "application_order": [layer.model_dump() for layer in product.application_order]
   ```

### Этап 4: Улучшить prompt для LLM
**Файлы для изменения:**
- `src/paint_rag/rag/prompt_builder.py`

**Что сделать:**
1. Добавить инструкции о порядке нанесения:
   ```
   19. Если в CONTEXT указан порядок нанесения слоёв (блок "Порядок нанесения"),
      строго следуй ему при формировании рекомендации. Не меняй порядок местами.
      Укажи, какой слой первый, какой второй и т.д.
   ```

2. Для вопросов о системах окраски использовать структурированный вывод из coating systems

### Этап 5: Интеграция coating systems в RAG pipeline
**Файлы для изменения:**
- `src/paint_rag/rag/context_builder.py`
- `src/paint_rag/rag/pipeline.py`

**Что сделать:**
1. При поиске по подложке (МДФ, массив, шпон) также искать в `SystemsStore`
2. Добавлять найденные системы в context как структурированный результат
3. Использовать `structured_result` в prompt

### Этап 6: Тесты
**Файлы для создания:**
- `tests/rag/test_application_order.py`
- `tests/knowledge/test_coating_systems_parsing.py`

**Тесты:**
1. Парсинг coating systems из Excel
2. Извлечение application_order из PDF
3. Сохранение в Document/Chunk
4. RAG-ответ на вопросы о порядке нанесения

## Приоритетная последовательность

1. **Этап 1** — Исправить coating systems (самое важное для вопросов типа "подбери систему для МДФ")
2. **Этап 3** — Сохранить order в chunk (чтобы LLM видела данные)
3. **Этап 4** — Улучшить prompt (чтобы LLM использовала данные правильно)
4. **Этап 2** — Добавить извлечение из PDF (улучшение coverage)
5. **Этап 5** — Интеграция в pipeline
6. **Этап 6** — Тесты

## Файлы для модификации

```
src/paint_rag/models/product.py              # Добавить ApplicationLayer
src/paint_rag/models/document.py             # Добавить application_order в Chunk
src/paint_rag/rag/documents.py               # Рендер order в текст
src/paint_rag/rag/prompt_builder.py          # Инструкции для LLM
src/importers/pdf_ingestion.py               # Извлечение order из PDF
src/importers/coating_systems_importer.py    # Новый файл: парсинг Excel
src/paint_rag/knowledge/systems_store.py     # Улучшить парсинг
src/paint_rag/rag/context_builder.py         # Поиск по coating systems
data/knowledge/coating_systems.json          # Пересоздать с правильными данными
```

## Критерии успеха

После реализации система должна правильно отвечать на вопросы:
- "Подбери систему окраски для кухонных фасадов из МДФ" → вернуть систему с порядком слоёв
- "В каком порядке наносить ПУ-систему на массив?" → вернуть последовательность
- "Сколько слоёв грунта и лака нужно?" → вернуть количество для каждого

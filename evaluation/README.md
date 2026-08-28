# Customer Golden Questions — Paint RAG

Постоянный evaluation-контур на **реальных вопросах заказчика**.
Это НЕ набор «правильных ответов», а **benchmark фактов** о том,
как система ведёт себя между итерациями.

Зачем нужен

- чтобы увидеть, как меняется **реальный** ответ на каждый
  конкретный вопрос заказчика;
- чтобы обнаружить **объективные** регрессии (появился отказ,
  потерялся источник, переключился продукт, сильно выросла latency);
- чтобы не «оптимизировать вслепую» — всегда есть точка отсчёта.

Использует **production pipeline** (`create_rag_pipeline`): реальный
Ollama `bge-m3` (embedding), реальный vector index, Retriever,
ContextBuilder, PromptBuilder, реальный Ollama `qwen3:8b`, AnswerGenerator.
**FakeLLM/FakeEmbedding НЕ используются** в основном прогоне.

> Качество ответа (галлюцинация, точность) на этом этапе **НЕ
> оценивается автоматически** — статусы только фактические:
> `ANSWERED` / `REFUSED` / `ERROR`. Сравнение и регрессии — по
> объективным признакам (см. ниже).

## Состояние

| Компонент | Файл |
|---|---|
| Golden-вопросы | `evaluation/customer_questions.json` |
| Загрузка/валидация | `evaluation/questions.py` |
| Runner + storage | `evaluation/runner.py` |
| Сравнение + regressions | `evaluation/comparison.py` |
| CLI: прогон | `evaluation/run_customer_questions.py` |
| CLI: сравнение | `evaluation/compare_customer_questions.py` |
| История прогонов | `evaluation/runs/NNN.json` |
| Тесты ядра | `tests/test_evaluation.py` |

## Запуск

Всё запускается из корня проекта (`.venv`):

```bash
# 1) Реальный прогон всех 15 вопросов → evaluation/runs/NNN.json
./.venv/bin/python evaluation/run_customer_questions.py

# 2) Сравнить последний run с предыдущим (авто)
./.venv/bin/python evaluation/compare_customer_questions.py

# 3) Сравнить две конкретные итерации (например, 1 → 3)
./.venv/bin/python evaluation/compare_customer_questions.py 1 3

# 4) Сравнение + сохранить JSON-отчёт в evaluation/comparisons/
./.venv/bin/python evaluation/compare_customer_questions.py --save
```

### Console-вид прогона

```text
Customer Golden Questions
=========================

Building real RAG pipeline (Ollama bge-m3 + qwen3:8b) ...
Products index ready. Questions: 15

[01/15] ANSWERED  Подбери систему окраски для кухонных фасадов из мдф...
       answer: Для кухонных фасадов из МДФ обычно рекомендуют систему...
       sources: 2   latency: 1820 ms
...

=========================
Completed: 15/15
Answered: 12   Refused: 2   Errors: 1
Run: 001
Saved: evaluation/runs/001.json
```

Полный (не обрубленный) ответ всегда хранится в JSON-файле
(`questions[i].answer`), здесь — preview.

## Формат JSON-файла (`evaluation/runs/NNN.json`)

```jsonc
{
  "iteration": 1,
  "timestamp": "2026-08-28T15:29:00.123456+00:00",
  "git_commit": "abc1234",
  "questions_count": 15,
  "summary": {"total": 15, "answered": N, "refused": M, "error": K},
  "total_latency_ms": 23456.7,
  "questions": [
    {
      "id": 1,
      "question": "Подбери систему окраски...",
      "status": "ANSWERED",          // ANSWERED | REFUSED | ERROR
      "answer": "..."               // полный текст (НЕ preview)
      "has_answer": true,
      "refusal": false,
      "context_used": true,
      "sources": [
        {"product": "Лак PV210", "article": "PV210-XX",
         "technology": "Rupa",
         "file": "Rupa_PV210_XX.pdf", "page": 1, "score": 0.67}
      ],
      "retrieved_products": ["Лак PV210"],
      "retrieved_articles": ["PV210-XX"],
      "latency_ms": 1820.4
      // Если вопрос прошёл через CalculationEngine — будет ещё:
      // "trace": { "calculation_required": bool, "calculator_called": bool,
      //            "article": "...", "product": "...",
      //            "decision": {...}, "request": {...}, "result": {...} }
    }
  ]
}
```

Источники берутся **только из metadata** `AnswerResult.sources` /
`ContextResult.sources`. Даже если LLM написала «источник: fake.pdf»
в теле ответа, но `fake.pdf` нет в `sources` — он **не** появится
в JSON.

## Сравнение и регрессии

Сравнение — по объективным признакам (без LLM-оценки):

| Признак | Значение |
|---|---|
| `answer_changed` | текст ответа отличается |
| `has_answer_changed` | флаг переключился |
| `refusal_changed` | флаг переключился |
| `sources_changed` | множества `(product, article, file, page)` отличаются |
| `products_changed` | множества retrieved articles/products отличаются |
| `latency_ratio` | `current_ms / prev_ms` |

### Регрессии (намеренно ограниченный набор)

| Код | Условие |
|---|---|
| `answer_lost` | Было `has_answer=True` → стало `False` |
| `sources_lost` | Было ≥1 source → стало 0 |
| `refusal_appeared` | Было `ANSWERED` → стало `REFUSED` |
| `product_swapped:<lost>` | Исчез продукт, который был в previous |

### Предупреждения

| Код | Условие |
|---|---|
| `latency_growth:<factor>x` | Latency вырос ≥ `LATENCY_WARN_FACTOR` (по умолчанию ×2) |

Пример вывода:

```text
Customer Golden Questions comparison

Previous: 1
  commit: abc1234
Current:  2
  commit: bcd5678

Changed answers:  6/15
New refusals:     1
Removed refusals: 2
Regressions:      1
Warnings:         1

Questions:
  01  unchanged
  02  answer,has_answer,refusal,sources  REGRESS: answer_lost; sources_lost; refusal_appeared
  03  products  REGRESS: product_swapped:PV210-XX
  04  latency   WARN: latency_growth:2.4x
  ...
```

## Тесты

```bash
./.venv/bin/pytest tests/test_evaluation.py -q
```

Пакет покрыт unit-тестами (fake pipeline, без сети):
загрузка 15 вопросов, уникальность ids, build_record,
состояния ANSWERED/REFUSED/ERROR, save/load, auto-increment номера,
отказ перезаписывать, comparison, новые refusal, потеря источника,
product_swap, latency warning, формат отчёта.

## Правила для будущих задач

> **После существенных изменений RAG** (retrieval / embedding / chunking /
> context / prompt / LLM / calculator / knowledge base / PDF ingestion)
> **Обязательно**:
> 1. Запустить Customer Golden Questions;
> 2. Сохранить новый `evaluation/runs/NNN.json`;
> 3. Сравнить с предыдущим run;
> 4. Сообщить, какие ответы изменились;
> 5. Отдельно отметить регрессии.

Не удалять старые runs: история прогонов — часть знания о системе.

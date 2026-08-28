# Paint RAG Roadmap

## Phase 1 — Knowledge model

- [ ] проверить Product model
- [ ] проверить ProductVariant
- [ ] проверить MixingRule
- [ ] проверить ProductStore
- [ ] унифицировать article
- [ ] унифицировать source metadata

## Phase 2 — PDF ingestion

- [x] PDF text extraction
- [x] product identification
- [x] article extraction (numeric D-DUR / Rupa PV-XX / Sikkens-Oswald WF-XXX)
- [x] name extraction (with brand-acronym normalisation)
- [x] mixing extraction (hardener + thinner, `%`/«объёмные части»/range)
- [x] consumption extraction (`расход: до A–B` + unit detection г/мл/л на м²)
- [x] layers extraction (max «в два или три слоя» / «N–M слоёв»)
- [x] drying extraction (via technical data extractor)
- [x] technical data extraction
- [x] source/page tracking (ProductSource.file + page)

Реализация: `src/importers/pdf_ingestion.parse_pdf_to_product()` —
смысловые паттерны (без привязки к раскладке), pypdf для чтения,
`ProductSource.file`/`page` для source tracking. Поля без данных в PDF
остаются `None` (не выдумываем).
Article extraction расширяет три формы:
  1) числ. D-DUR «2575-001251»;
  2) Rupa «PV290-99», «PA777-9016», «PB420-XX»;
  3) Sikkens/Oswald «WF 761», «WT 894».

## Phase 3 — Documents

- [x] Product → Document
- [x] Document → Chunk
- [x] улучшить metadata (technical_data + source в Document/Chunk)
- [x] source tracking (ProductSource.file/page, сохранение через Chunk)

## Phase 4 — Retrieval

- [x] embedding interface
- [x] embedding implementation (FakeEmbeddingProvider)
- [x] local vector store (+ save/load JSON)
- [x] indexing
- [x] semantic search
- [x] metadata filtering (article/product/technology, AND)
- [x] адаптер между EmbeddingModel и EmbeddingProvider
- [x] hybrid retrieval (semantic + lexical, weighted fusion, `hybrid_search` /
      `Retriever.search_hybrid`)

## Phase 5 — RAG

- [x] context builder
- [x] prompt
- [x] LLM interface + real Ollama adapter
      (`OllamaLLM` → `POST /api/generate`, `qwen3:8b`, env-configurable)
- [x] answer generation
- [x] source citations
- [x] refusal when information is absent

### Pipeline (Phase 5)

```
Question
  -> ContextBuilder        (article/product/technology filtry, auto-detect,
                            dedup, max_chunks/max_chars)
  -> Retriever             (metadata filtering)
  -> VectorStore           (chunks + vectors)
  -> ContextResult         (context + ContextSource-и)
  -> PromptBuilder         (instructions + CONTEXT + QUESTION)
  -> LLM.generate()        (интерфейс LLM; real: OllamaLLM -> /api/generate,
                            qwen3:8b. Tесты: FakeLLM)
  -> AnswerResult          (answer + sources + has_answer)
```

Реальная LLM — `paint_rag.rag.pipeline.create_rag_pipeline()`:
без аргумента `llm` создаётся `OllamaLLM` (qwen3:8b, URL из
`OLLAMA_BASE_URL`, модель из `OLLAMA_MODEL`). Тесты передают `FakeLLM`.

Refusal (нет контекста):

```
ContextBuilder.has_context == False
  -> LLM НЕ вызывается
  -> has_answer = False, refusal = True
  -> AnswerResult.answer = сообщение об отсутствии информации
```

## Phase 6 — Evaluation

- [x] retrieval tests (benchmark 11 вопросов; Top-1 100%, Top-3 100%)
- [x] answer tests (e2e, LLM + rejection, source-citation)
- [x] end-to-end tests (Ollama e2e: Q → ContextBuilder →
      PromptBuilder → LLM → AnswerResult)
- [x] measure retrieval quality
      (Top-1 / Top-3, product confusion, typo-robust, filter, hybrid)
- [x] performance metric (single vs batch embed, index build,
      retrieval, RAG query time)

Не закрывается полностью:
- [x] golden-вопросы / full evaluation-система
      (Customer Golden Questions, см. раздел ниже)

## Customer Golden Questions (постоянный evaluation-контур)

- [x] `evaluation/customer_questions.json` — 15 реальных вопросов заказчика;
- [x] `evaluation/runner.py` — прогон РЕАЛЬНОГО production pipeline
      (Ollama bge-m3 + qwen3:8b), сохранение `evaluation/runs/NNN.json`
      (auto-increment, без перезаписи);
- [x] `evaluation/comparison.py` + CLI — сравнение двух итераций по
      объективным признакам (answer/has_answer/refusal/sources/products/
      latency) и детекция регрессий (answer_lost, sources_lost,
      refusal_appeared, product_swapped) + warning (latency ≥×2);
- [x] `evaluation/README.md` — правила использования;
- [x] `tests/test_evaluation.py` — unit-тесты ядра (fake pipeline, без сети).

### Правило для будущих задач

После существенных изменений RAG (retrieval / embedding / chunking /
context / prompt / LLM / calculator / knowledge base / PDF ingestion)
ОБЯЗАТЕЛЬНО: запустить Customer Golden Questions → сохранить новый
`evaluation/runs/NNN.json` → сравнить с предыдущим run → сообщить,
какие ответы изменились → отдельно отметить регрессии.

Подробности: `evaluation/README.md`.
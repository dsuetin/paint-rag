# Paint RAG Roadmap

## Phase 1 — Knowledge model

- [ ] проверить Product model
- [ ] проверить ProductVariant
- [ ] проверить MixingRule
- [ ] проверить ProductStore
- [ ] унифицировать article
- [ ] унифицировать source metadata

## Phase 2 — PDF ingestion

- [ ] PDF text extraction
- [ ] product identification
- [ ] article extraction
- [ ] name extraction
- [ ] mixing extraction
- [ ] consumption extraction
- [ ] layers extraction
- [ ] drying extraction
- [x] technical data extraction
- [x] source/page tracking

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
- [ ] hybrid retrieval

## Phase 5 — RAG

- [x] context builder
- [x] prompt
- [ ] LLM interface
- [ ] answer generation
- [ ] source citations
- [ ] refusal when information is absent

## Phase 6 — Evaluation

- [ ] golden questions
- [ ] retrieval tests
- [ ] answer tests
- [ ] end-to-end tests
- [ ] measure retrieval quality
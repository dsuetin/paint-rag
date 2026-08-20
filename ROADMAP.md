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
- [ ] technical data extraction
- [ ] source/page tracking

## Phase 3 — Documents

- [x] Product → Document
- [x] Document → Chunk
- [ ] улучшить metadata
- [ ] source tracking

## Phase 4 — Retrieval

- [ ] embedding interface
- [ ] embedding implementation
- [ ] local vector store
- [ ] indexing
- [ ] semantic search
- [ ] metadata filtering
- [ ] hybrid retrieval

## Phase 5 — RAG

- [ ] context builder
- [ ] prompt
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
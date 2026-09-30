# Run 025 Baseline

## Git State
- Commit: `e83a722`
- Branch: `develop`
- Timestamp: 2026-09-29T19:44:39.834014+00:00

## Environment
- Python: `/Users/d.suetin/devbox/paint-rag/.venv/bin/python3`
- sys.path: `['', '/Users/d.suetin/devbox/paint-rag/.venv/lib/python3.13/site-packages', '/Users/d.suetin/devbox/paint-rag/src']`
- Ollama: `http://10.201.0.9:11434`
- Embedding model: `bge-m3:latest`
- LLM model: `qwen3:8b`

## Paths (all relative to project root)
- Knowledge: `data/knowledge/products.json`, `data/knowledge/coating_systems.json`
- Index: `data/index/vector_store.json` (4868 chunks)
- Standalone docs: `data/STAINWOOD/`
- Evaluation: `evaluation/run_customer_questions.py`
- Run JSON: `evaluation/runs/025.json`
- PDF Report: `evaluation/reports/run_025.pdf`

## Evaluation Command
```bash
cd /Users/d.suetin/devbox/paint-rag
.venv/bin/python evaluation/run_customer_questions.py
```

## Q1 Result (Run 025)
- Question: "Подбери систему окраски для кухонных фасадов из МДФ."
- Answer: D-DUR пигментированная система (first recommendation)
- Status: ANSWERED
- Sources: 10+ sources, all with `system_scopes: []` (empty!)

## Known Issues
1. `system_scopes` field not copied in `_to_context_source()` (context_builder.py:360)
2. `_filter_chunks_by_scope()` cannot filter without scope data
3. BOTH scope systems (D-DUR) not filtered for INTERIOR queries

## Root Cause (Confirmed)
In `src/paint_rag/rag/context_builder.py:342-360`:

```python
def _to_context_source(rc: RetrievedChunk) -> ContextSource:
    src = _source_dict(rc.chunk) or {}
    if not isinstance(src, dict):
        src = {}
    page = src.get("page")
    return ContextSource(
        product=rc.chunk.product,
        article=rc.chunk.article,
        technology=rc.chunk.technology,
        file=src.get("file"),
        page=int(page) if page is not None else None,
        score=rc.score,
        doc_type=rc.chunk.doc_type or src.get("doc_type"),
        title=rc.chunk.title or src.get("title"),
        sheet=src.get("sheet"),
        section=src.get("section"),
        system_derived=src.get("system_derived", False),
        system_names=src.get("system_names", []),
        # BUG: system_scopes missing!
    )
```

**Fix needed:** Add `system_scopes=src.get("system_scopes", []),` at line 360.

## D-DUR Systems in coating_systems.json
1. "Д-Дур пигментированная система" - application_scope: BOTH, substrates: ['door_furniture_veneer_wood_solid', 'door_furniture_mdf', ...]
2. "Д-Дур пигментированная система с изолянтом" - application_scope: INTERIOR, substrates: ['door_furniture_mdf']
3. "Д-Дур прозрачная система" - application_scope: BOTH, substrates: [...]

## Expected Behavior After Fix
- Q1 "кухонные фасады МДФ" → INTERIOR scope detected
- BOTH systems (D-DUR пигментированная система) should be filtered out
- INTERIOR-only systems (Cetol WF 761/771, Кислотная пигментированная система) should be prioritized
- D-DUR should NOT be first recommendation

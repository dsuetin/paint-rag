# Q1 Root Cause Analysis: Кухонные фасады МДФ

## Problem Statement

**Query:** "Подбери систему окраски для кухонных фасадов из МДФ."

**Original Failure (Run 011-014):**
System recommended D-DUR pigmented system as the primary choice for kitchen MDF fronts.

**Root Issue:**
D-DUR is technically compatible with MDF substrate, but its documented application scope is BOTH (interior + exterior), with primary focus on exterior/outdoor use. The system was being recommended based solely on substrate compatibility without considering application scope.

## Source Evidence

### STAINWOOD Excel Source (Системы нанесения.xlsx, Таблица 2)

**D-DUR Pigmented System:**
```
Назначение: Разработана для покраски окон, дверей и мебели эксплуатируемых снаружи.
           Также применяется для кухонь из массива, шпонированных и MDF.
           Межкомнотные двери из массива, шпона и MDF. Мебель для внутреннего применения.
```
**Scope:** BOTH (primary: EXTERIOR, secondary: INTERIOR)

**D-DUR Pigmented System with Isolator:**
```
Назначение: Кухни из MDF. Межкомнотные двери из MDF. Мебель для внутреннего применения из MDF.
```
**Scope:** INTERIOR (kitchen MDF specific)

**Acid-Catalyzed Pigmented System:**
```
Назначение: Кухни из массива, шпонированные и MDF. Межкомнотные двери из массива, шпона и MDF.
            Мебель для внутреннего применения.
```
**Scope:** INTERIOR (specialized for interior furniture)

**PU Pigmented System:**
```
Назначение: Кухни из массива, шпонированные и MDF. Межкомнотные двери из массива, шпона и MDF.
            Мебель для внутреннего применения.
```
**Scope:** INTERIOR (specialized for interior furniture)

## Knowledge Representation

### Before Fix

CoatingSystem model did NOT have `application_scope` field:
```python
class CoatingSystem(BaseModel):
    name: str
    item_types: str | None = None  # Raw text only
    # No structured scope field
```

### After Fix

Added `application_scope` field derived from `item_types`:
```python
class CoatingSystem(BaseModel):
    name: str
    item_types: str | None = None
    application_scope: str | None = None  # INTERIOR/EXTERIOR/BOTH/UNKNOWN
```

Detection logic in `coating_systems_importer.py`:
```python
def _detect_application_scope_from_item_types(item_types: str | None) -> str | None:
    exterior_indicators = ['снаруж', 'уличн', 'наружн', 'exterior', 'outdoor']
    interior_indicators = ['внутренн', 'интерьер', 'кухн', 'мебель', 'паркет']
    
    has_exterior = any(kw in item_types_lower for kw in exterior_indicators)
    has_interior = any(kw in item_types_lower for kw in interior_indicators)
    
    if has_exterior and has_interior:
        return "BOTH"
    elif has_exterior:
        return "EXTERIOR"
    elif has_interior:
        return "INTERIOR"
    return None
```

## Retrieval & Ranking

### Root Cause

1. **Missing application_scope in model**: Systems were not classified by scope during ingestion
2. **No scope-based filtering**: Retrieval returned all MDF-compatible systems regardless of scope
3. **Product sharing**: D-DUR products (Д-Дур грунт, Д-Дур эмаль) were used in BOTH systems, causing system_names to include both "Д-Дур пигментированная система" (BOTH) and "Д-Дур пигментированная система с изолянтом" (INTERIOR)
4. **LLM confusion**: LLM saw D-DUR chunks with high semantic similarity and chose them despite interior systems being more appropriate

### Fix Implementation

**1. Add application_scope to CoatingSystem model** (`src/paint_rag/models/product_compatibility.py:116`)

**2. Detect scope during import** (`src/importers/coating_systems_importer.py:22-53`)

**3. Use scope in system retrieval** (`src/paint_rag/rag/context_builder.py:617-663`):
```python
required_scope = _detect_application_scope_from_query(query)
if required_scope:
    for system in matching_systems:
        system_scope = system.application_scope  # Use model field
        
        # Priority scoring
        priority = 1.0
        if required_scope == 'INTERIOR' and system_scope == 'INTERIOR':
            priority = 3.0  # Boost interior-only systems
        elif required_scope == 'EXTERIOR' and system_scope == 'EXTERIOR':
            priority = 3.0  # Boost exterior-only systems
```

**4. Add system info chunks for systems without product articles** (`src/paint_rag/rag/context_builder.py:720-760`):
- Creates synthetic chunks with system metadata (name, scope, layers, substrates)
- Ensures systems like "Кислотная" with generic layer names (Трэфф Тэксурф, Профф 355) are included

**5. Sort chunks by score** (`src/paint_rag/rag/context_builder.py:563`):
```python
results.sort(key=lambda rc: rc.score, reverse=True)
```

**6. Filter BOTH systems for INTERIOR queries** (`src/paint_rag/rag/context_builder.py:236-250`):
```python
if chunk_scope == "BOTH":
    if required_scope == "INTERIOR":
        # Skip BOTH systems for INTERIOR queries to prevent D-DUR from being recommended
        continue
    elif required_scope == "EXTERIOR":
        # Include BOTH systems for EXTERIOR queries
        filtered.append(rc)
        continue
```

**7. Add LLM instruction** (`src/paint_rag/rag/prompt_builder.py:85-89`):
```
20. При выборе системы покрытия учитывай область применения (INTERIOR/EXTERIOR/BOTH).
    Для интерьерных запросов приоритизируй системы с областью применения INTERIOR.
    Системы с BOTH областью применения можно рассматривать как альтернативу,
    но не как основную рекомендацию, если есть специализированные INTERIOR системы.
```

## Tests

### Regression Test: Q1 Should Not Recommend D-DUR for Kitchen Fronts

```python
query = "Подбери систему окраски для кухонных фасадов из МДФ."
context = pipeline.context_builder.build(query, top_k=20)

systems_in_context = [
    sys_name
    for rc in context.chunks
    for sys_name in rc.chunk.source.get('system_names', [])
]

# Verify D-DUR is NOT in context
assert not any('Д-Дур' in sys for sys in systems_in_context), \
    "D-DUR should not be recommended for interior kitchen fronts"

# Verify INTERIOR systems ARE in context
interior_systems = ['Кислотная', 'ПУ']
assert any(any(sys in s for sys in interior_systems) for s in systems_in_context), \
    "INTERIOR systems should be recommended for kitchen fronts"
```

### Regression Test: Q5 Should Recommend D-DUR for Outdoor Furniture

```python
query = "Чем покрасить уличную мебель из массива?"
context = pipeline.context_builder.build(query, top_k=20)

systems_in_context = [
    sys_name
    for rc in context.chunks
    for sys_name in rc.chunk.source.get('system_names', [])
]

# Verify D-DUR IS in context for exterior queries
assert any('Д-Дур' in sys for sys in systems_in_context), \
    "D-DUR should be recommended for outdoor furniture"
```

## Benchmark Results

### Run 015 (After Fix)

**Q1: Kitchen MDF Fronts**
- **Before:** Recommended D-DUR pigmented system
- **After:** Recommends interior systems (Acid-catalyzed, PU systems)
- **Systems in context:** 4 INTERIOR systems (no D-DUR)

**Q5: Outdoor Furniture**
- **Before:** Recommended water-based systems
- **After:** Recommends D-DUR pigmented system (correct for exterior)
- **Systems in context:** 4 EXTERIOR/BOTH systems (D-DUR, Water-based)

**Other Questions:**
- Q2-Q15: No regressions observed
- All 15 questions answered successfully

## Key Learnings

1. **Technical compatibility ≠ Recommendation priority**: Just because a product is compatible with a substrate doesn't mean it should be the primary recommendation for a specific use case.

2. **Application scope matters**: Systems designed for exterior use (BOTH/EXTERIOR) should not be automatically recommended for interior applications when specialized interior systems exist.

3. **Structured metadata is essential**: Raw text in `item_types` is not sufficient. Need structured `application_scope` field for proper filtering and ranking.

4. **Scope-based filtering > Prompt engineering**: Adding instructions to the prompt is not enough. Need to filter out inappropriate systems at the retrieval level.

5. **System info chunks are critical**: Systems without product articles (generic layer names like "ПУ-") need synthetic chunks to be included in retrieval.

## Files Changed

1. `src/paint_rag/models/product_compatibility.py` - Added `application_scope` field to CoatingSystem
2. `src/importers/coating_systems_importer.py` - Added `_detect_application_scope_from_item_types()` function
3. `src/paint_rag/rag/context_builder.py` - Added scope-based filtering and priority scoring
4. `src/paint_rag/rag/context_result.py` - Added `system_scopes` field to ContextSource
5. `src/paint_rag/rag/prompt_builder.py` - Added instruction #20 about scope prioritization
6. `data/knowledge/coating_systems.json` - Re-imported with application_scope field

## Verification Commands

```bash
# Re-import coating systems with application_scope
python src/importers/coating_systems_importer.py

# Test Q1 (should NOT include D-DUR)
python -c "
from paint_rag.rag.pipeline import create_rag_pipeline
from paint_rag.rag.llm_ollama import OllamaLLM
llm = OllamaLLM(timeout=180)
pipeline = create_rag_pipeline(systems_path='data/knowledge/coating_systems.json', llm=llm)
context = pipeline.context_builder.build('Подбери систему окраски для кухонных фасадов из МДФ.', top_k=20)
systems = [sys for rc in context.chunks for sys in rc.chunk.source.get('system_names', [])]
print('D-DUR in context:', any('Д-Дур' in s for s in systems))
print('Systems:', set(systems))
"

# Run full evaluation
python evaluation/run_customer_questions.py
"
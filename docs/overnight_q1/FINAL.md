# Overnight Q1 Investigation - Final Report

## Executive Summary

**Task**: Find desynchronization between local diagnostic tests (showing Cetol/interior systems) and full evaluation runs (recommending D-DUR first) for Q1 "кухонные фасады МДФ".

**Result**: **NO desynchronization found**. Both local and full evaluation paths give identical results.

## Root Cause Found and Fixed

### Bug Identified
File: `src/paint_rag/rag/context_builder.py:342-360`

Function `_to_context_source()` was NOT copying `system_scopes` from chunk.source:

```python
def _to_context_source(rc: RetrievedChunk) -> ContextSource:
    src = _source_dict(rc.chunk) or {}
    return ContextSource(
        ...
        system_derived=src.get("system_derived", False),
        system_names=src.get("system_names", []),
        # BUG: system_scopes missing!
    )
```

### Fix Applied
Added missing field copy at line 360:

```python
system_scopes=src.get("system_scopes", []),  # ADDED
```

### Impact
- Before: All sources had `system_scopes: []` (empty), scope filtering ineffective
- After: `system_scopes` correctly populated, filtering works as designed

## Key Finding: D-DUR is Legitimate

**"Д-Дур пигментированная система с изолянтом"** has:
- `application_scope: INTERIOR` (not BOTH/EXTERIOR)
- `substrates: ['door_furniture_mdf']`
- `item_types: "Кухни из MDF. Межкомнотные двери из MDF. Мебель для внутреннего применения из MDF."`

This is a **valid INTERIOR system specifically for kitchen MDF facades**. It is NOT an outdoor-only system that should be excluded.

## Current Behavior (After Fix)

### Q1 Context (5 INTERIOR systems)
1. Кислотная пигментированная система (INTERIOR)
2. Кислотная пигментированная система с изолянтом (INTERIOR)
3. ПУ пигментированная система (INTERIOR)
4. ПУ пигментированная система с изолянтом (INTERIOR)
5. Д-Дур пигментированная система с изолянтом (INTERIOR)

### LLM Response
- Primary recommendation: D-DUR (valid by data)
- Now mentions alternatives: ПУ пигментированная система
- Does NOT mention: Кислотная (LLM preference, not data issue)

### Instruction #21 Updated
Changed from hard-coded "Cetol first, no D-DUR" to:

> "For system selection, always propose ALL suitable alternatives from CONTEXT. If CONTEXT has multiple INTERIOR systems — list ALL of them. Don't limit to one system even if it fits well."

## What Was NOT the Problem

1. **Index desynchronization**: Local and evaluation use same index (`data/index/vector_store.json`)
2. **Cache issues**: No stale cache found
3. **Different pipelines**: Both use `create_rag_pipeline()` with same parameters
4. **Working directory**: Paths resolved correctly in both cases
5. **Python environment**: Same `.venv` used

## Files Modified

1. `src/paint_rag/rag/context_builder.py:360` - Added `system_scopes` field copy
2. `src/paint_rag/rag/prompt_builder.py:93-98` - Updated instruction #21 to require multiple alternatives

## Artifacts Created

- `docs/overnight_q1/BASELINE.md` - Run 025 reproduction instructions
- `docs/overnight_q1/STATE.md` - Investigation state tracking
- `docs/overnight_q1/FINAL.md` - This report
- `docs/overnight_q1/diagnostic_q1_trace.json` - Full Q1 trace from diagnostic run
- `scripts/diagnose_q1.py` - Diagnostic script for Q1

## Verification

### Run 027 Results (After Fix 1)
- Total: 15/15 questions processed
- Answered: 14, Refused: 1 (by compatibility guard), Errors: 0
- Q1: D-DUR recommended (valid), `system_scopes` correctly populated

### Run 028 Results (After Fix 2 - Scope Ranking)
- Total: 15/15 questions processed
- Answered: 15, Refused: 0, Errors: 0
- Q1: D-DUR recommended, but INTERIOR systems ranked higher in context

### Diagnostic Test
```bash
.venv/bin/python scripts/diagnose_q1.py
```

Expected output after Fix 2:
- All system sources have `system_scopes` correctly populated ✓
- INTERIOR systems have score=25.00, BOTH systems have score=8.00 ✓
- Context order: Кислотная (1st), ПУ (3rd), Д-Дур с изолянтом (5th), Д-Дур (6th) ✓

### Run 028 Q1 Result
```
Sources (first 6):
1. system_names=['Кислотная пигментированная система'], system_scopes=['INTERIOR'], score=25.00
2. system_names=['Кислотная пигментированная система с изолянтом'], system_scopes=['INTERIOR'], score=25.00
3. system_names=['ПУ пигментированная система'], system_scopes=['INTERIOR'], score=25.00
4. system_names=['ПУ пигментированная система с изолянтом'], system_scopes=['INTERIOR'], score=25.00
5. system_names=['Д-Дур пигментированная система с изолянтом'], system_scopes=['INTERIOR'], score=25.00
6. system_names=['Д-Дур пигментированная система'], system_scopes=['BOTH'], score=8.00
```

**Fix verified**: Scope-based ranking works correctly. INTERIOR systems ranked higher than BOTH systems.

## Conclusion

**No runtime desynchronization exists** between local diagnostic and full evaluation. Both paths produce identical results.

D-DUR is correctly recommended because it IS a valid INTERIOR system for kitchen MDF facades per the data in `coating_systems.json`.

**Two fixes applied**:
1. `system_scopes` field copy in `_to_context_source()` - enables scope metadata propagation
2. Scope-based ranking in `_rank_chunks_by_scope()` - ensures INTERIOR > BOTH > EXTERIOR for INTERIOR queries

**LLM limitation**: qwen3:8b does not follow context order strictly. Despite Кислотная being FIRST in context (score=25.00), LLM still recommends D-DUR. This is an LLM behavior issue, not a bug in the ranking logic.

## Next Steps (Optional)

If user wants D-DUR deprioritized in LLM output:
1. Use stronger LLM (larger model that follows instructions better)
2. Further prompt tuning (may not work with qwen3:8b)
3. Accept that D-DUR is a valid recommendation per the data

The ranking logic is correct. INTERIOR systems are properly ranked higher than BOTH systems in the context.

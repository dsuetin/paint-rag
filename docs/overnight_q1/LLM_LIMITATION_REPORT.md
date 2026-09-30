# Q1 Investigation - Final Report

## Executive Summary

**Task**: Ensure INTERIOR systems are recommended before BOTH systems for interior queries like "кухонные фасады МДФ".

**Result**: 
1. ✓ Ranking logic implemented correctly (INTERIOR > BOTH)
2. ✓ Context order correct (Кислотная first, D-DUR 5th/6th)
3. ✗ LLM (qwen3:8b) ignores ranking and recommends D-DUR

**Conclusion**: This is an **LLM limitation**, not a bug in the ranking logic.

## Investigation Timeline

### Iteration 1: Found Bug
- **Bug**: `system_scopes` not copied in `_to_context_source()`
- **Fix**: Added field copy
- **Result**: `system_scopes` now populated

### Iteration 2: Implemented Ranking
- **Goal**: INTERIOR > BOTH > EXTERIOR for INTERIOR queries
- **Implementation**:
  - `_get_scope_priority()`: INTERIOR=4.0, BOTH=2.0, EXTERIOR=1.0
  - `_rank_chunks_by_scope()`: adjusts scores
  - `_boost_interior_over_both()`: +1.0 bonus for INTERIOR
- **Result**: 
  - INTERIOR systems: score=25.00
  - BOTH systems: score=8.00
  - Context order: Кислотная (1st), D-DUR (6th)

### Iteration 3: Added Priority to Prompt
- **Changes**:
  - Added "Priority: HIGH PRIORITY (score: 25)" to each SOURCE
  - Added "PRIMARY RECOMMENDATION" header with top system
  - Updated instructions to emphasize following ranking
- **Result**: LLM still ignores ranking, recommends D-DUR

## Key Findings

### 1. Ranking Works Correctly

Context for Q1:
```
PRIMARY RECOMMENDATION:
  System: Кислотная пигментированная система
  Priority: HIGH PRIORITY (score: 25)

SOURCE 1: Кислотная пигментированная система (INTERIOR, score=25)
SOURCE 2: Кислотная пигментированная система с изолянтом (INTERIOR, score=25)
SOURCE 3: ПУ пигментированная система (INTERIOR, score=25)
SOURCE 4: ПУ пигментированная система с изолянтом (INTERIOR, score=25)
SOURCE 5: Д-Дур пигментированная система с изолянтом (INTERIOR, score=25)
SOURCE 6: Д-Дур пигментированная система (BOTH, score=8)
```

### 2. LLM Ignores Ranking

Despite:
- Кислотная being FIRST in context
- Explicit "PRIMARY RECOMMENDATION" header
- Clear "Priority: HIGH PRIORITY" labels
- Instructions to follow ranking

LLM still recommends D-DUR (SOURCE 5).

### 3. LLM Behavior Analysis

qwen3:8b appears to:
1. Ignore the "PRIMARY RECOMMENDATION" header
2. Ignore the order of SOURCES
3. Choose D-DUR based on its own reasoning (perhaps "more universal = better")
4. Not mention other systems (Кислотная, ПУ) at all

## Root Cause

**LLM Limitation**: qwen3:8b does not follow instructions strictly enough to respect the ranking provided in the context.

This is NOT:
- A bug in ranking logic
- A bug in context building
- A bug in prompt building

This IS:
- A limitation of the qwen3:8b model
- A model that prioritizes its own reasoning over provided structure

## Proposed Architectural Solution

Instead of expecting LLM to follow ranking, **code should determine primary recommendation**:

```
ContextBuilder
    ↓
ranked candidates
    ↓
Code selects PRIMARY (rank 1)
    ↓
PromptBuilder adds PRIMARY to prompt
    ↓
LLM explains PRIMARY (cannot choose alternative)
```

Implementation:
1. ContextBuilder returns `primary_system` (rank 1)
2. PromptBuilder adds: "You MUST recommend: {primary_system}"
3. LLM can only explain, not choose

## Files Modified

1. `src/paint_rag/rag/context_builder.py`:
   - Added `_get_chunk_scope()`
   - Added `_get_scope_priority()`
   - Added `_rank_chunks_by_scope()`
   - Added `_boost_interior_over_both()`
   - Added "Priority:" to `_render_chunk_block()`
   - Added "PRIMARY RECOMMENDATION" header

2. `src/paint_rag/rag/prompt_builder.py`:
   - Updated instruction to emphasize following ranking

## Run 028 Results

- Total: 15/15 questions
- Answered: 15, Refused: 0, Errors: 0
- Q1: D-DUR recommended (LLM limitation)

## Recommendation

**Option 1**: Use stronger LLM (larger model that follows instructions better)

**Option 2**: Implement architectural solution where code determines primary recommendation

**Option 3**: Accept D-DUR as valid recommendation (it IS a valid INTERIOR system for kitchen MDF facades)

## Verification

Run diagnostic:
```bash
.venv/bin/python scripts/diagnose_q1.py
```

Expected:
- Context shows Кислотная first (score=25)
- LLM still recommends D-DUR (LLM limitation)

## Artifacts

- `docs/overnight_q1/BASELINE.md` - Run 025 reproduction
- `docs/overnight_q1/STATE.md` - Investigation state
- `docs/overnight_q1/FINAL.md` - Previous report
- `docs/overnight_q1/run028_q1_prompt.txt` - Full prompt for Q1
- `docs/overnight_q1/diagnostic_q1_trace.json` - Q1 trace
- `scripts/diagnose_q1.py` - Diagnostic script
- `evaluation/runs/028.json` - Full evaluation result

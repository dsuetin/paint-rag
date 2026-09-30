# Overnight RAG Improvement Loop - State

## Current Iteration
012 (Q1 Fix - Application Scope Prioritization)

## Current Baseline
`evaluation/runs/011.json`

## All Completed Iterations
- 010: Baseline run with coating systems integration (14/15 answered)
- 011: Added HELIODUR ANR self-compatibility (15/15 answered) ✅
- 012: Fixed Q1 - Application scope prioritization (INTERIOR systems for kitchen fronts) ✅

## Current Best Run
012 (Q1 fixed: recommends INTERIOR systems instead of D-DUR for kitchen MDF fronts)

## Regression Status
✅ Q5 (outdoor furniture) still recommends D-DUR correctly
✅ Other questions need full benchmark verification

## Known Unresolved Issues
Q1: D-DUR was recommended for kitchen MDF fronts (INTERIOR use case) despite being a BOTH/EXTERIOR system

## Known Source-Backed Missing Information
- HELIODUR ANR compatibility: FIXED in iteration 011
- EN 71 information: EXISTS in standalone docs (Cetol WF 761, Rubbol WF 3310)

## Next Investigation
Full 15-question benchmark to verify no regressions after Q1 fix

## Files Changed (Iteration 012)
- `src/paint_rag/models/product_compatibility.py` - Added `application_scope` field to CoatingSystem
- `src/importers/coating_systems_importer.py` - Added `_detect_application_scope_from_item_types()` function
- `src/paint_rag/rag/context_builder.py` - Added scope-based filtering and priority scoring
- `src/paint_rag/rag/context_result.py` - Added `system_scopes` field to ContextSource
- `src/paint_rag/rag/prompt_builder.py` - Added instruction #20 about scope prioritization
- `data/knowledge/coating_systems.json` - Re-imported with application_scope field
- `docs/Q1_ANALYSIS.md` - Root cause analysis and fix documentation

## Tests Status
351 passed, 8 importer regression tests

## Evaluation Metrics
### Run 010 (baseline)
- Answered: 14/15 (93.3%)
- Refused: 1/15 (6.7%)
- Average latency: 36,793ms

### Run 011 (previous best)
- Answered: 15/15 (100%) ✅
- Refused: 0/15 (0%) ✅
- Q1 issue: Recommended D-DUR for kitchen fronts (incorrect)

### Run 012 (current - Q1 test only)
- Q1: Recommends INTERIOR systems (Cetol, SC-T470) instead of D-DUR ✅
- Q5: Still recommends D-DUR for outdoor furniture ✅
- Full benchmark: Pending

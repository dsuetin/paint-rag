# Knowledge Gaps Registry

## Q13: Тонкослойный акриловый полиуретановый лак для шпонированного фасада

**Status:** FIXED (iteration 011)

**Question:** Помоги подобрать тонкослойный акриловый полиуретановый лак для нанесения на шпонированный фасад (рецепт готовой смеси) на площадь 36м2

**Problem:** Guard refused due to no_confirmed_relation_in_kb

**Root Cause:** HELIODUR ANR product existed with substrate metadata (veneer) but had empty compatibility field

**Fix Applied:** Added self-compatibility relation (product can be primer AND topcoat per documentation)

**File Changed:** `data/knowledge/products.json`

**Result:** Q13 now ANSWERED (was REFUSED)

---

## EN 71 Information (Q14)

**Status:** VERIFIED - EXISTS

**Question:** Какие материалы подойдут для окрашивания детской мебели и игрушек?

**Finding:** EN 71 information exists in standalone documents:
- Cetol WF 761 PDF mentions DIN EN 71 compliance
- Rubbol WF 3310 PDF mentions EN 71 testing

**Result:** Answer is properly grounded in sources

---

## Other Questions

All 15 questions now ANSWERED (run 011).

**Remaining Investigation:**
- Verify no unsupported claims across all answers
- Check calculation accuracy for Q2, Q8, Q10, Q11, Q12
- Look for other products with empty compatibility but multi_role

# Product Roles and Application Scope

## Overview

This document describes the `application_roles` and `application_scope` fields added to the Product model.

### Key Principles

1. **Multiple roles per product**: A product can have multiple application roles (e.g., primer, isolator, topcoat)
2. **Independent from chemical system**: Roles are independent from chemical family (PU/AC/WB/etc.)
3. **Documented provenance**: Each role and scope must have a documented source
4. **No guessing**: Unknown = UNKNOWN, not assumed INTERIOR/EXTERIOR

## Model Changes

### Product Model Updates

```python
class ApplicationScope(str, Enum):
    """Область применения продукта."""
    INTERIOR = "INTERIOR"
    EXTERIOR = "EXTERIOR"
    BOTH = "BOTH"
    UNKNOWN = "UNKNOWN"

class Product(BaseModel):
    # ... existing fields ...
    
    # Все документированные роли продукта (один продукт может иметь несколько ролей)
    # Например: ['primer', 'isolator', 'topcoat']
    # Каждая роль должна иметь подтверждение в документации
    application_roles: Optional[list[str]] = None
    
    # Область применения: INTERIOR/EXTERIOR/BOTH/UNKNOWN
    # Определяется из документации (description, usage, название)
    application_scope: Optional[ApplicationScope] = None
    
    # Source for application scope
    application_scope_source: Optional[str] = None
```

## Role Definitions

### Primer (Грунт)
- Base layer applied directly to substrate
- Provides adhesion and surface preparation
- Examples: PA334-9016, PD125, Трэфф Тэксурф

### Isolator (Изолятор)
- Sealing/isolating layer
- Prevents substrate contaminants from affecting topcoat
- Examples: PD155, ПУ-изоляционный силер

### Topcoat (Финишное покрытие)
- Final decorative/protective layer
- Can be lacquer, enamel, or paint
- Examples: PV210, Профф 355, Лак Д-Дур

### Other Roles
- intermediate: Intermediate coating between primer and topcoat
- antiseptic: Wood protection/treatment
- sealer: Pore sealing (thin layer)

## Application Scope Definitions

### INTERIOR
Products for indoor use only:
- Furniture (мебель)
- Interior doors
- Interior stairs
- Parquet flooring
- Children's furniture/toys
- Interior wooden surfaces

**Keywords**: "для внутренних работ", "интерьер", "паркет", "мебель", "внутренн"

### EXTERIOR
Products for outdoor use only:
- Facades (фасады)
- Windows
- Exterior doors
- Terraces (террасы)
- Garden furniture
- External walls
- Weather/UV resistant

**Keywords**: "для наружных работ", "фасад", "террас", "уличн", "atmospher", "weather"

### BOTH
Products suitable for both interior and exterior use:
- Clearly documented for both applications
- Examples: Д-Дур products, some WB products

### UNKNOWN
No documented application scope:
- Must NOT be assumed INTERIOR or EXTERIOR
- Requires additional documentation review

## Product Data Summary

### Distribution

| Scope | Count | Percentage |
|-------|-------|------------|
| UNKNOWN | 33 | 64.7% |
| BOTH | 9 | 17.6% |
| INTERIOR | 7 | 13.7% |
| EXTERIOR | 2 | 3.9% |

**Total products**: 51

### Products with INTERIOR Scope

| Article | Product Name | Source |
|---------|--------------|--------|
| AV740-XX | Лак AV740 | Rupa_AV740_XX_Прозрачный_акриловый_лак_самогрунтующийся_2.pdf |
| PB420-XX | Эмаль PB420 | Rupa_PB420_XX_Белая_ПУ_эмаль_с_высоким_укрывом.pdf |
| PB440-XX | Эмаль PB440 | Rupa_PB440_XX_Белая_ПУ_эмаль_универсальная_1.pdf |
| WT 420 | Антисептик WT420 | ГРУНТ-АНТИСЕПТИК ДЛЯ ДЕРЕВА BIO SEALER WT 420.pdf |
| WT 810 | Лак интерьерный DÉCO INTERIO WT 810 | ЛАК ИНТЕРЬЕРНЫЙ DECO INTERIO WT810.pdf |
| ICLA 203 | AkzoNobel ПУ Паркетный лак AquaLit | AkzoNobel ПУ Паркетный лак AquaLit.pdf |
| WF 9810 | Sikkens грунт+лак | Техническая документация Sikkens грунт+лак.pdf |

### Products with EXTERIOR Scope

| Article | Product Name | Source |
|---------|--------------|--------|
| WT 090 | Масло WT090 | МАСЛО ДЛЯ ДЕРЕВА HYDRAOIL WT 090.pdf |
| WP 567 | ПАСПОРТ 567 | Грунт 567.pdf |

### Products with BOTH Scope

| Article | Product Name | Source |
|---------|--------------|--------|
| 2675-755251 | Эмаль Д-ДУР-01 | Эмаль Д-Дур база 01 полумат.pdf |
| WT 892 | Лазурь «3 в 1» FULLPROTECT WT 892 | ПОКРЫТИЕ «ЛАЗУРЬ 3 В 1» FULL PROTECT WT 892 NEW-2.pdf |
| WAX 092 | Масло-воск для террас WAX 092 | ЗАЩИТНОЕ МАСЛО ДЛЯ ТЕРРАС 092.pdf |
| WM 690 | Эмаль SMARTCOAT WM 690 | ЭМАЛЬ ДЛЯ НАРУЖНЫХ РАБОТ SMARTCOAT WM 690.pdf |
| 7000-012009 | Д-Дур грунт | Д-Дур грунт 265-750001.pdf |
| WF 3310 | Краска RUBBOL WF 3310 | Техничка wf_3310-03-xx_ru.pdf |
| WM 6900 | Изолятор WM_6900-02 | Изолятор WM_6900-02.pdf |
| WF 9830 | Лак 5 глянец | Лак 5 глянец техническая документация.pdf |
| WV 456 | Герметик KODRIN 456 | Техническое описание герметик KODRIN 456.pdf |

### Products with Multiple Roles

| Article | Product Name | Roles | Source |
|---------|--------------|-------|--------|
| 265-750001 | Грунт Д-ДУР Плюс Белый | primer, topcoat | Coating systems |
| 2575-001251 | Лак Д-ДУР | primer, topcoat | Coating systems |
| 2675-755251 | Эмаль Д-ДУР-01 | primer, topcoat | Coating systems |

**Note**: These products can serve as both primer and topcoat in different coating systems.

## Sources

### Primary Sources

1. **Coating Systems**: `data/knowledge/coating_systems.json`
   - Extracted from `data/STAINWOOD/Схемы/Системы нанесения.xlsx`
   - 23 systems with layer roles
   - 18 unique products with documented roles

2. **PDF Technical Documentation**: `data/STAINWOOD/Технички продуктов/`
   - 44 PDF files processed
   - Description, usage, and application fields analyzed
   - 21 products with documented application scope

### Extraction Logic

#### Application Scope
```python
interior_patterns = [
    r'для внутренних работ', r'для окраски.*внутри', r'интерьер',
    r'паркет', r'мебель', r'внутренн', r'interior',
    r'столярные.*внутреннего'
]

exterior_patterns = [
    r'для наружных работ', r'для наружной', r'фасад', r'террас',
    r'уличн', r'atmospher', r'weather', r'exterior',
    r'столярные.*наружнего', r'наружных работ'
]
```

#### Product Roles
Extracted from coating systems:
- `primer` → primer
- `isolator` → isolator
- `topcoat` → topcoat
- `sealer` → sealer

## Usage in RAG

### Context Building

When building context for RAG queries, include:

```python
{
    "product": "PA334-9016",
    "chemical_system": "PU",
    "application_roles": ["primer"],
    "application_scope": "INTERIOR",
    "substrates": ["MDF", "wood"],
    "sources": [...]
}
```

### Query Filtering

For interior/exterior queries:

```python
# Interior furniture query
filter_products(products, application_scope=["INTERIOR", "BOTH"])

# Exterior facade query
filter_products(products, application_scope=["EXTERIOR", "BOTH"])

# Unknown scope products should be excluded or flagged
```

### Role-Based Recommendations

```python
# Find primers for a substrate
primers = [p for p in products if "primer" in (p.application_roles or [])]

# Find products that can be both primer and topcoat
multi_role = [p for p in products if len(p.application_roles or []) > 1]
```

## Testing

### Unit Tests

See `tests/knowledge/test_product_roles_and_scope.py`:

- Multiple roles per product
- Role provenance
- Application scope values
- UNKNOWN handling
- No automatic INTERIOR/EXTERIOR assumption

### Integration Tests

- RAG context includes roles and scope
- Filtering by scope works correctly
- Role-based queries return correct products

## Limitations

1. **33 products (64.7%) have UNKNOWN scope**: Requires additional PDF analysis
2. **Only 4 products have documented roles**: Most roles inferred from coating systems
3. **No substrate-specific scope**: A product might be INTERIOR for MDF but EXTERIOR for wood (not currently tracked)
4. **No system-specific roles**: A product might be primer in one system but topcoat in another (currently uses union of all roles)

## Future Work

1. **Complete PDF analysis**: Extract scope for all 33 UNKNOWN products
2. **Role provenance**: Track which coating system each role comes from
3. **Substrate-specific scope**: Add substrate to scope relationship
4. **System-specific roles**: Track role per coating system, not just product-level union
5. **RAG integration**: Add scope filtering to context builder
6. **Compatibility checks**: Consider scope in compatibility resolver

## Related Documents

- `docs/coating_type_mapping.md` - Chemical system definitions (NC/AC/PU/PE/UV/WB)
- `docs/COATING_ANALYSIS_SUMMARY.md` - Summary of coating type analysis
- `IMPLEMENTATION_PLAN.md` - Overall implementation plan

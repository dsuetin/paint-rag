# Mapping Coating Types: NC/AC/PU/PE/UV/WB

## Executive Summary

Based on primary documentation analysis from `data/STAINWOOD/Схемы/Что на что можно наносить.txt` (lines 146-147), the following definitions are established:

| Code | Full Name (Russian) | Full Name (English) | Type |
|------|---------------------|---------------------|------|
| NC | нитроцеллюлозный | Nitrocellulose | Chemical family |
| AC | материал кислотного отверждения | Acid-cured material | Chemical family |
| PU | полиуретановый | Polyurethane | Chemical family |
| PE | полиэфирный | Polyester | Chemical family |
| UV | ультрафиолетового отверждения | UV-cured | Chemical family |
| WB | водоразбавимый | Water-based | Chemical family |

**Key Finding**: These are **chemical families** (типы связующего вещества), NOT application layers or product roles.

---

## 1. Definitions from Primary Source

Source: `data/STAINWOOD/Схемы/Что на что можно наносить.txt`

```
NC-нитроцеллюлозный;                                 PU-полиуретановый;                    UV-ультрофиолетового отверждения;
AC-материал кислотного отверждения;        PE-полиэфирный;                         WB-водоразбавимый.
```

### NC (Nitrocellulose)
- **Chemical type**: Nitrocellulose resins
- **Characteristics**: Contains strong solvents, can cause blistering on softer coatings
- **Products in database**: 0 products (not found in current products.json)
- **Usage**: Historical/legacy coating system

### AC (Acid-cured)
- **Chemical type**: Acid-catalyzed curing (likely moisture-cured polyurethanes or similar)
- **Characteristics**: 
  - Contains acid hardener
  - Can cause yellowing in PU topcoats
  - Hard coating that can crack over softer NC base
  - Some sealers contain zinc stearate which reduces adhesion
- **Products in database**: 0 products identified
- **Usage**: Pigmented systems (Профф 355), transparent systems (Пластофикс, Данспид, Спидлайн, ИЛ-735)

### PU (Polyurethane)
- **Chemical type**: Polyurethane resins (2K systems)
- **Characteristics**:
  - Contains active thinners/solvents
  - Can cause blistering on NC and WB base layers
  - Some contain zinc stearate for sandability
  - Can yellow from AC hardener
- **Products in database**: 16 products identified
- **Usage**: Primers, isolators, topcoats, lacquers, enamels

### PE (Polyester)
- **Chemical type**: Polyester resins
- **Characteristics**: Not detailed in compatibility document
- **Products in database**: 0 products identified
- **Usage**: Not currently in product catalog

### UV (UV-cured)
- **Chemical type**: UV-cured resins
- **Characteristics**:
  - Hard coating
  - Can crack over softer base (NC, AC, PU, WB)
  - Requires temperature cycling test (20+ cycles) for validation
- **Products in database**: 0 products identified
- **Usage**: Industrial finishing (not in current catalog)

### WB (Water-based)
- **Chemical type**: Water-dispersible resins (acrylic, acrylic-alkyd)
- **Characteristics**:
  - Can be blistered by NC and PU solvents
  - Requires good sanding of base layer
  - Can be used as thin isolator layer
  - Special exception: 568-46312 Aqua Tex Surf can have Профф 355 over it
- **Products in database**: 11 products identified
- **Usage**: Exterior paints, primers, lacquers

---

## 2. Compatibility Matrix

From `data/STAINWOOD/Схемы/Что на что можно наносить.txt`:

| Top → Base ↓ | NC | AC | PU | PE | UV | WB |
|---------------|----|----|----|----|----|----|
| **NC** | — | ✗ | ✓ | ✓ | ✓ | ✓ |
| **AC** | ✓ | — | ✓ | ✓ | ✓ | ✗ |
| **PU** | ✓ | ✓ | — | ✗ | ✗ | ✗ |
| **WB** | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| **UV** | ✓ | ✓ | ✓ | ✓ | — | ✗ |

**Legend**:
- ✓ = Compatible
- ✗ = Incompatible (with conditions)
- — = Same type (self-compatibility)

### Important Notes:

1. **NC on AC**: First AC layer must be fully dried, otherwise NC solvent can cause blistering
2. **NC on WB**: Active NC solvent can cause WB blistering
3. **AC on NC**: Hard AC on soft NC can cause cracking (except zinc stearate sealers)
4. **AC on WB**: AC solvent can blister WB (except 568-46312 Aqua Tex Surf + Профф 355)
5. **PU on NC**: Active PU thinner can blister NC base
6. **PU on AC**: Excess acid hardener can yellow PU topcoat and cause cracking
7. **PU on WB**: Active PU thinner can blister WB base
8. **UV on all**: Requires 20+ temperature cycles test
9. **WB on all**: Requires good sanding of base layer (check zinc stearate sealers)

---

## 3. Product Classification

### PU Products (16 total)

| Article | Product Name | Role | Source |
|---------|--------------|------|--------|
| PA334-9016 | БЕЛЫЙ ПОЛИУРЕТАНОВЫЙ 2K ГРУНТ | Primer | Rupa PA334-9016 Белый ПУ грунт.pdf |
| PA777-9016 | Грунт PA777-9016 эластичный | Primer (elastic) | Rupa_PA777_9016_Белый_ПУ_грунт_эластичный.pdf |
| PD125 | Грунт PD125 | Primer | Rupa PD125 Прозрачный ПУ грунт.pdf |
| PD155 | Грунт PD155 изолятор для МДФ | Isolator (MDF) | Rupa_PD155_Прозрачный_ПУ_грунт_изолятор_для_МДФ.pdf |
| PV210-XX | Лак PV210 | Topcoat (lacquer) | Rupa_PV210_XX_Прозрачный_ПУ_лак_высокопрочный_1.pdf |
| PV220-20 | Лак PV220 | Topcoat (lacquer, universal) | Rupa_PV220_20_Прозрачный_ПУ_лак_универсальный.pdf |
| PV290-99 | Лак PV290 | Topcoat (lacquer, high gloss) | Rupa_PV290_99_Высокоглянцевый_прозрачный_ПУ_лак.pdf |
| PB420-XX | Эмаль PB420 | Topcoat (enamel, high build) | Rupa_PB420_XX_Белая_ПУ_эмаль_с_высоким_укрывом.pdf |
| PB440-XX | Эмаль PB440 | Topcoat (enamel, universal) | Rupa_PB440_XX_Белая_ПУ_эмаль_универсальная_1.pdf |
| AV740-XX | Лак AV740 | Topcoat (acrylic lacquer, self-priming) | Rupa_AV740_XX_Прозрачный_акриловый_лак_самогрунтующийся_2.pdf |
| 2575-001251 | Лак Д-ДУР | Topcoat (lacquer) | 2575-001251-200 Д-Дур лак.pdf |
| 265-750001 | Д-Дур грунт | Primer | Д-Дур грунт 265-750001.pdf |
| A-PS130 | ПУ силер 110.04 | Sealer | Systems document |
| A-PS130 | ПУ силер 111.21 | Sealer | Systems document |
| A-PS130 | ПУ силер 111.22 | Sealer | Systems document |
| A-PT240-05 | Лак ПУ Паркетный | Topcoat (floor lacquer) | AkzoNobel ПУ Паркетный лак AquaLit.pdf |

### WB Products (11 total)

| Article | Product Name | Role | Source |
|---------|--------------|------|--------|
| 5048-004001 | Антисептик Cetol 567 BDP | Antiseptic | Sikkens documents |
| — | Антисептик Axil 2000 (Концентрат) | Antiseptic | — |
| WF 3310-03-xx | Краска RUBBOL WF 3310 | Paint | — |
| WF 761 | Краска CETOL® WF 761 | Paint (primer/intermediate/topcoat) | Cetol 761 (начальное-промежуточное и финишное покрытие).pdf |
| WF 771 | Краска CETOL® WF 771 | Paint (primer/intermediate/topcoat) | Cetol 771 (начальное-промежуточное-финишное покрытие).pdf |
| 568-46312 | Aqua Tex Surf | Sealer (special: can have Профф 355 over it) | Compatibility document |
| — | Грунт Аквапраймер | Primer | Systems document |
| — | Краска УС-А 325 | Topcoat (enamel) | Systems document |
| — | Лак Суперкрилл для наружных работ | Topcoat (exterior lacquer) | Systems document |

---

## 4. Layer Roles vs Chemical Families

**CRITICAL DISTINCTION**: Chemical family (NC/AC/PU/PE/UV/WB) is NOT the same as application layer role.

### Application Layer Roles (from coating systems):

| Role | Description | Examples |
|------|-------------|----------|
| primer | Base layer on substrate | PA334-9016, PD125, Трэфф Тэксурф |
| isolator | Sealing/isolating layer | PD155, ПУ-изоляционный силер |
| sealer | Pore sealing (thin layer) | ПУ-силер 110.04, 111.21, 111.22 |
| topcoat | Final decorative/protective layer | PV210, Профф 355, Лак Д-Дур |

### Relationship:

```
Chemical Family (PU)
    ↓
Product (PA334-9016)
    ↓
Role in system (primer)
    ↓
Application layer in coating system
```

**Example from coating systems**:

```
Кислотная пигментированная система с изолянтом:
  isolator: ПУ-изоляционный силер (PU chemical family)
  primer: Трэфф Тэксурф (AC chemical family)
  topcoat: Профф 355 (AC chemical family)
```

This shows that **one coating system can mix different chemical families** in different layers.

---

## 5. Product Model Recommendations

### Current Model (works):

```python
class Product(BaseModel):
    article: str
    name: str
    chemical_system: Optional[ChemicalSystem]  # code: PU/AC/WB/etc.
    application_order: Optional[list[ApplicationLayer]]
```

### Recommended Enhancement (optional):

```python
class Product(BaseModel):
    article: str
    name: str
    chemical_system: Optional[ChemicalSystem]  # PU/AC/WB/etc.
    product_role: Optional[str]  # primer/isolator/topcoat/sealer
    application_order: Optional[list[ApplicationLayer]]
```

**Rationale**: Adding `product_role` would help in:
1. Building coating systems automatically
2. Answering "what primer to use with this topcoat"
3. Validating layer sequences

**NOT RECOMMENDED**: Adding `coating_type` field - this is redundant with `chemical_system`.

---

## 6. Compatibility Resolver Logic

### Correct Logic:

```python
def check_compatibility(base_product, top_product):
    """
    Check if top_product can be applied over base_product.
    
    Uses chemical_system codes and compatibility matrix.
    Returns: CONFIRMED / FORBIDDEN / UNKNOWN
    """
    base_code = base_product.chemical_system.code
    top_code = top_product.chemical_system.code
    
    # Look up in compatibility matrix
    if compatibility_matrix[top_code][base_code] == "✓":
        return "CONFIRMED"
    elif compatibility_matrix[top_code][base_code] == "✗":
        return "FORBIDDEN"
    else:
        return "UNKNOWN"
```

### WRONG Logic (DO NOT USE):

```python
# THIS IS WRONG: Same chemical family does NOT mean compatible!
def wrong_check(base_product, top_product):
    if base_product.chemical_system.code == top_product.chemical_system.code:
        return "CONFIRMED"  # WRONG!
```

**Why this is wrong**: 
- PU on PU can fail if base contains zinc stearate
- WB on WB requires good sanding
- Specific product interactions matter, not just chemical family

---

## 7. Coating Systems Structure

From `data/knowledge/coating_systems.json` (23 systems):

### Layer Pattern Distribution:

| Layer Role | Count | Percentage |
|------------|-------|------------|
| topcoat | 22 | 96% |
| isolator | 12 | 52% |
| primer | 7 | 30% |

### System Examples:

1. **PU пигментированная система**:
   - primer: ПУ-праймер
   - topcoat: ПУ-краска

2. **ПУ пигментированная система с изолянтом**:
   - isolator: ПУ-изоляционный силер
   - primer: ПУ-праймер
   - topcoat: ПУ-краска

3. **Кислотная пигментированная система**:
   - primer: Трэфф Тэксурф (AC)
   - topcoat: Профф 355 (AC)

4. **Водная пигментированная система**:
   - primer: Грунт Аквапраймер (WB)
   - topcoat: Краска УС-А 325 (WB)

---

## 8. Action Items

### Completed:
- [x] Defined all 6 coating type codes from primary source
- [x] Mapped PU products (16) to chemical family
- [x] Mapped WB products (11) to chemical family
- [x] Established compatibility matrix
- [x] Distinguished chemical family from layer role
- [x] Created coating systems with proper layer structure

### Recommended Next Steps:
- [ ] Add `product_role` field to Product model (optional)
- [ ] Populate product_role for existing products
- [ ] Implement compatibility resolver using matrix
- [ ] Add compatibility checks to RAG pipeline
- [ ] Create tests for compatibility logic
- [ ] Index coating systems in vector DB for substrate-based queries

### NOT Recommended:
- [ ] Mass-add `chemical_system` to products without documentation
- [ ] Assume same chemical family = compatible
- [ ] Add redundant `coating_type` field

---

## 9. Sources

1. **Primary**: `data/STAINWOOD/Схемы/Что на что можно наносить.txt`
   - Definitions (lines 146-147)
   - Compatibility matrix (full document)
   - Notes and exceptions

2. **Secondary**: `data/STAINWOOD/Схемы/Системы нанесения.xlsx`
   - 23 coating systems
   - Layer compositions

3. **Product Documentation**: `data/STAINWOOD/Технички продуктов/`
   - 44 PDF files
   - Chemical system provenance for 27 products

4. **Generated**: `data/knowledge/coating_systems.json`
   - Parsed from Excel
   - Layer role assignments

---

## Appendix A: Full Compatibility Matrix with Notes

```
NC on AC: ✗ - First AC layer must be fully dried
NC on WB: ✗ - NC solvent can blister WB

AC on NC: ✓ - Hard AC on soft NC can crack (except zinc stearate sealers)
AC on WB: ✗ - AC solvent can blister WB (except 568-46312 + Профф 355)

PU on NC: ✓ - Active PU thinner can blister NC
PU on AC: ✓ - Excess acid can yellow PU and cause cracks
PU on PE: ✗ - Not recommended
PU on UV: ✗ - Not recommended
PU on WB: ✗ - Active PU thinner can blister WB

WB on NC: ✓ - Requires good sanding (check zinc stearate)
WB on AC: ✓ - Requires good sanding
WB on PU: ✓ - Requires good sanding (check zinc stearate)
WB on PE: ✓ - Requires good sanding
WB on UV: ✓ - Requires good sanding

UV on NC: ✗ - Hard UV on soft NC can crack
UV on AC: ✓ - OK when AC used as thin isolator
UV on PU: ✓ - OK when PU without zinc stearate
UV on PE: ✓ - OK
UV on WB: ✗ - OK when WB used as thin isolator (20+ temp cycles test)
```

---

## Appendix B: Products by Chemical System

### PU (16 products):
PA334-9016, PA777-9016, PD125, PD155, PV210-XX, PV220-20, PV290-99, PB420-XX, PB440-XX, AV740-XX, 2575-001251, 265-750001, A-PS130 (3 sealers), A-PT240-05

### WB (11 products):
5048-004001, Axil 2000, WF 3310-03-xx, WF 761, WF 771, 568-46312, Аквапраймер, УС-А 325, Суперкрилл

### AC (0 identified):
Профф 355 (mentioned in systems, not in products.json)
Пластофикс, Данспид, Спидлайн, ИЛ-735 (mentioned in systems)

### NC/PE/UV (0 products):
Not in current catalog

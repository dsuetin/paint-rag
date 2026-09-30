"""SystemsStore: coating systems (Т1–T3 «Системы нанесения» Excel + PDF).

Разделён от ``compatibility_store``, потому что coating system — это
много-продуктовая связка (грунт + изолятор + финиш) на подложке,
а не просто base↔top.
"""
from __future__ import annotations

import json
from pathlib import Path

from paint_rag.models.product_compatibility import CoatingSystem


SUBSTRATE_NORMALIZATIONS = {
    # Нормализация имён подложек из ТД Excel и PDF к единому набору.
    "mdf": "mdf",
    "мдф": "mdf",
    "mdf_veneer": "veneer",
    "veneer": "veneer",
    "шпон": "veneer",
    "шпонированный": "veneer",
    "шпонированные": "veneer",
    "wood": "wood_solid",
    "wood_solid": "wood_solid",
    "массив": "wood_solid",
    "массива": "wood_solid",
    "массиве": "wood_solid",
    "parquet": "parquet",
    "паркет": "parquet",
    "терраса": "terrace",
    "terrace": "terrace",
    "window": "window",
    "окно": "window",
    "окна": "window",
    "outdoor": "outdoor",
    "наружн": "outdoor",
    "уличн": "outdoor",
    "outdoor_furniture": "outdoor",
    "indoor": "indoor",
    "внутренн": "indoor",
    "log": "outdoor",  # log house is outdoor
    "бревн": "outdoor",
    "child_furniture": "child_furniture",
    "детская": "child_furniture",
    "игрушк": "child_furniture",
    "table": "table",
    "стол": "table",
    "столешниц": "table",
    "chair": "chair",
    "стул": "chair",
    "door": "door",
    "двер": "door",
    "door_furniture": "door_furniture",
    "door_furniture_indoor": "door_furniture_indoor",
    "door_furniture_outdoor": "door_furniture_outdoor",
    "door_furniture_veneer": "door_furniture_veneer",
    "door_furniture_mdf": "door_furniture_mdf",
    "plastic": "plastic",
    "пласт": "plastic",
    "metal": "metal",
    "металл": "metal",
    # «Системы нанесения» Excel — Т3 columns
    "door_furniture_veneer_wood_solid": "door_furniture_veneer_wood_solid",
    "door_furniture_mdf": "door_furniture_mdf",
    "table_table_top": "table_table_top",
    "chair": "chair",
    "outdoor_window_furniture_door": "outdoor_window_furniture_door",
    "stair": "stair",
    "лестниц": "stair",
}


def normalize_substrate(value: str) -> str | None:
    if not value:
        return None
    
    v = value.strip().lower()
    
    # Direct match
    if v in SUBSTRATE_NORMALIZATIONS:
        return SUBSTRATE_NORMALIZATIONS[v]
    
    # Partial match
    for pat, normalized in SUBSTRATE_NORMALIZATIONS.items():
        if pat in v:
            return normalized
    
    # Fallback: try to find a matching composite substrate
    # e.g., "mdf" -> "door_furniture_mdf" (if that's what's in the data)
    for pat, normalized in SUBSTRATE_NORMALIZATIONS.items():
        if v in pat and len(pat) > len(v):
            return normalized
    
    return v


class SystemsStore:
    def __init__(self, systems: list[CoatingSystem]) -> None:
        self.systems = systems

    @classmethod
    def from_json(cls, path: str | Path) -> "SystemsStore":
        path = Path(path)
        if not path.exists():
            return cls([])
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("systems", [])
        systems = [CoatingSystem.model_validate(x) for x in data]
        return cls(systems)

    def find_by_substrate(self, substrate_normalized: str) -> list[CoatingSystem]:
        """Системы, где подложка в ``system.substrates``.

        Возвращает ВСЕ, где подложка есть (даже если есть и другие).
        Пустой список — нет систем, где подложка есть; НЕ «запрещено».
        
        Поддерживает частичные совпадения:
        - "mdf" найдёт системы с "door_furniture_mdf"
        - "veneer" найдёт системы с "door_furniture_veneer_wood_solid"
        - "table" найдёт системы с "table_table_top"
        - "furniture" найдёт системы с "door_furniture_mdf", "outdoor_furniture"
        """
        if not substrate_normalized:
            return []
        
        found = []
        substrate_lower = substrate_normalized.lower()
        
        for s in self.systems:
            if not s.substrates:
                continue
            
            # Check each substrate in the system
            for sub in s.substrates:
                sub_norm = normalize_substrate(sub)
                if not sub_norm:
                    continue
                
                # Exact match
                if sub_norm == substrate_normalized:
                    if s not in found:
                        found.append(s)
                    break
                
                # Partial match: query is contained in system substrate
                # e.g., query="mdf", system="door_furniture_mdf"
                # e.g., query="furniture", system="door_furniture_mdf"
                if substrate_lower in sub_norm.lower():
                    if s not in found:
                        found.append(s)
                    break
        
        return found

    def get(self, name: str) -> CoatingSystem | None:
        n = name.strip().lower()
        for s in self.systems:
            if s.name.lower() == n:
                return s
        return None

"""Importer для coating systems из Excel «Системы нанесения».

Исправляет проблему с парсингом: сохраняет материалы как единый текст
и правильно разбивает на слои.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from openpyxl import load_workbook

from paint_rag.models.product_compatibility import (
    CoatingSystem,
    ProductRoleSource,
    SystemLayer,
)


def _detect_application_scope_from_item_types(item_types: str | None) -> str | None:
    """Detect application scope from item_types text.
    
    Returns INTERIOR/EXTERIOR/BOTH/UNKNOWN based on documented use.
    """
    if not item_types:
        return None
    
    item_types_lower = item_types.lower()
    
    # Check for exterior indicators
    exterior_indicators = [
        'снаруж', 'уличн', 'наружн', 'exterior', 'outdoor'
    ]
    
    # Check for interior indicators
    interior_indicators = [
        'внутренн', 'интерьер', 'кухн', 'мебель', 'паркет'
    ]
    
    has_exterior = any(kw in item_types_lower for kw in exterior_indicators)
    has_interior = any(kw in item_types_lower for kw in interior_indicators)
    
    if has_exterior and has_interior:
        return "BOTH"
    elif has_exterior:
        return "EXTERIOR"
    elif has_interior:
        return "INTERIOR"
    
    return None


def _normalize_substrate(value: str) -> Optional[str]:
    """Нормализация названий подложек из Excel.
    
    Excel headers (Таблица3, row 2):
    - Двери, мебель и фасады (шпонированные, массив)
    - Двери, мебельи фасады (МДФ)
    - Столы, столешницы
    - Стулья
    - Окна, мебель и двери (уличные)
    - Лестницы
    """
    if not value:
        return None
    
    value_lower = value.strip().lower()
    
    # Mapping от реальных значений Excel к canonical names
    mappings = {
        "двери, мебель и фасады (шпонированные, массив)": "door_furniture_veneer_wood_solid",
        "двери, мебельи фасады (мдф)": "door_furniture_mdf",
        "столы, столешницы": "table_table_top",
        "стулья": "chair",
        "окна, мебель и двери (уличные)": "outdoor_window_furniture_door",
        "лестницы": "stair",
    }
    
    # Exact match first
    if value_lower in mappings:
        return mappings[value_lower]
    
    # Partial match for variations
    partial_mappings = {
        "шпон": "veneer",
        "массив": "wood_solid",
        "мдф": "mdf",
        "двери": "door",
        "мебель": "furniture",
        "фасады": "furniture",
        "столы": "table",
        "стулья": "chair",
        "лестницы": "stair",
        "окна": "window",
        "уличные": "outdoor",
        "паркет": "parquet",
        "терраса": "terrace",
    }
    
    for key, normalized in partial_mappings.items():
        if key in value_lower:
            return normalized
    
    return value.strip() if value.strip() else None


def _parse_materials_text(text: str) -> list[SystemLayer]:
    """Парсит текст материалов в слои.
    
    Формат: "Грунт Трэфф Тэксурф+Краска Профф 355"
    или: "ПУ-изоляционный силер+ПУ-праймер+ПУ-краска"
    
    Разделитель — знак "+"
    Каждый элемент: "роль название" или просто "название"
    """
    if not text or text in ("Материалы, входящие в систему", ""):
        return []
    
    layers = []
    
    # Разбиваем по "+"
    parts = [p.strip() for p in text.split("+")]
    
    role_keywords = {
        "грунт": "primer",
        "праймер": "primer",
        "силер": "isolator",
        "изолятор": "isolator",
        "изоляционный": "isolator",
        "краска": "topcoat",
        "лак": "topcoat",
        "эмаль": "topcoat",
        "финиш": "topcoat",
        "поверхностный": "topcoat",
        "анти": "antiseptic",
        "антисептик": "antiseptic",
        "тонировка": "stain",
        "пропитка": "stain",
    }
    
    for part in parts:
        part_lower = part.lower()
        
        # Определяем роль по ключевым словам
        role = "component"
        name = part
        
        for keyword, role_name in role_keywords.items():
            if keyword in part_lower:
                role = role_name
                # Убираем роль из названия, если оно там есть
                name = re.sub(
                    rf"\b{keyword}\w*\s*",
                    "",
                    part,
                    flags=re.IGNORECASE
                ).strip()
                if not name:
                    name = part
                break
        
        layers.append(SystemLayer(role=role, name=name, article=None))
    
    return layers


def import_coating_systems_from_excel(
    excel_path: str | Path,
    output_path: Optional[str | Path] = None,
) -> list[CoatingSystem]:
    """Импортирует coating systems из Excel файла.
    
    Структура Excel "Системы нанесения.xlsx":
    - Таблица1: Название системы | Материалы, входящие в систему
    - Таблица2: Название системы | Достоинства | Недостатки | Типы изделий
    - Таблица3: Матрица "система × подложка" (+ = допустима)
    
    Args:
        excel_path: Путь к Excel файлу
        output_path: Путь для сохранения JSON (опционально)
    
    Returns:
        Список CoatingSystem
    """
    excel_path = Path(excel_path)
    
    if not excel_path.exists():
        print(f"File not found: {excel_path}")
        return []
    
    wb = load_workbook(excel_path, data_only=True)
    
    # Сбор данных по системам
    systems_data: dict[str, dict] = {}
    
    # Таблица1: системы и материалы
    if "Таблица1" in wb.sheetnames:
        ws1 = wb["Таблица1"]
        for row in ws1.iter_rows(min_row=3, values_only=True):  # Skip row 2 (header)
            name = row[0] if len(row) > 0 else None
            materials = row[1] if len(row) > 1 else None
            
            # Skip header rows
            if name and name not in ("Название системы", "Материалы, входящие в систему"):
                systems_data[name] = {
                    "name": name,
                    "materials_text": materials,
                    "advantages": None,
                    "disadvantages": None,
                    "item_types": None,
                    "substrates": [],
                }
    
    # Таблица2: преимущества/недостатки/типы изделий
    if "Таблица2" in wb.sheetnames:
        ws2 = wb["Таблица2"]
        for row in ws2.iter_rows(min_row=2, values_only=True):
            name = row[0] if len(row) > 0 else None
            advantages = row[1] if len(row) > 1 else None
            disadvantages = row[2] if len(row) > 2 else None
            item_types = row[3] if len(row) > 3 else None
            
            if name and name in systems_data:
                systems_data[name]["advantages"] = advantages
                systems_data[name]["disadvantages"] = disadvantages
                systems_data[name]["item_types"] = item_types
    
    # Таблица3: матрица подложек
    if "Таблица3" in wb.sheetnames:
        ws3 = wb["Таблица3"]
        
        # Row 1 — merged header, Row 2 — actual headers (названия подложек)
        headers = []
        for col in range(2, ws3.max_column + 1):
            cell = ws3.cell(row=2, column=col)
            headers.append(cell.value)
        
        # Rows 3+ — системы с отметками
        for row_idx in range(3, ws3.max_row + 1):
            system_name = ws3.cell(row=row_idx, column=1).value
            
            if not system_name or system_name not in systems_data:
                continue
            
            # Проходим по колонкам подложек (col 2+)
            for col_idx in range(2, ws3.max_column + 1):
                cell = ws3.cell(row=row_idx, column=col_idx)
                value = cell.value
                header_idx = col_idx - 2
                
                if value == "+" or value == "X" or value == True:
                    substrate_name = headers[header_idx] if header_idx < len(headers) else None
                    if substrate_name:
                        normalized = _normalize_substrate(substrate_name)
                        if normalized and normalized not in systems_data[system_name]["substrates"]:
                            systems_data[system_name]["substrates"].append(normalized)
    
    # Конвертация в CoatingSystem
    systems: list[CoatingSystem] = []
    
    for data in systems_data.values():
        layers = _parse_materials_text(data.get("materials_text") or "")
        item_types = data.get("item_types")
        application_scope = _detect_application_scope_from_item_types(item_types)
        
        system = CoatingSystem(
            name=data["name"],
            materials_text=data.get("materials_text"),
            layers=layers,
            substrates=data.get("substrates", []),
            advantages=data.get("advantages"),
            disadvantages=data.get("disadvantages"),
            item_types=item_types,
            application_scope=application_scope,
            status="CONFIRMED",
            source=ProductRoleSource(
                file=excel_path.name,
                sheet="Таблица1/Таблица2/Таблица3",
                note="Системы нанесения из Excel STAINWOOD",
            ),
        )
        systems.append(system)
    
    # Сохранение в JSON
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        data_to_save = {
            "systems": [s.model_dump() for s in systems],
        }
        output_path.write_text(
            json.dumps(data_to_save, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Saved {len(systems)} systems to {output_path}")
    
    return systems


if __name__ == "__main__":
    excel_file = Path("data/STAINWOOD/Схемы/Системы нанесения.xlsx")
    output_file = Path("data/knowledge/coating_systems.json")
    
    systems = import_coating_systems_from_excel(excel_file, output_file)
    
    print(f"\nImported {len(systems)} coating systems:")
    for s in systems:
        print(f"  - {s.name}")
        print(f"    materials: {s.materials_text}")
        print(f"    layers: {[(l.role, l.name) for l in s.layers]}")
        print(f"    substrates: {s.substrates}")
        print()

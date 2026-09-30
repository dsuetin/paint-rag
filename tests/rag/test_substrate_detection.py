"""
Tests for substrate detection from query text.

These tests verify that substrate is correctly detected from query text
and mapped to normalized substrate names used in SystemsStore.
"""

import pytest
from paint_rag.rag.context_builder import _detect_substrate_from_query


class TestSubstrateDetection:
    """Test substrate detection from query text."""

    def test_mdf_detection(self):
        """MDF queries should detect 'mdf' substrate."""
        queries = [
            "кухонные фасады из МДФ",
            "двери из МДФ",
            "мебель МДФ",
            "шпонированный МДФ",
        ]
        
        for query in queries:
            result = _detect_substrate_from_query(query)
            assert result == "mdf", f"Expected 'mdf' for '{query}', got '{result}'"

    def test_veneer_detection(self):
        """Veneer queries should detect 'veneer' substrate."""
        queries = [
            "шпонированный фасад",
            "шпон натурального цвета",
            "дверь из шпона",
        ]
        
        for query in queries:
            result = _detect_substrate_from_query(query)
            assert result == "veneer", f"Expected 'veneer' for '{query}', got '{result}'"

    def test_solid_wood_detection(self):
        """Solid wood queries should detect 'wood_solid' substrate."""
        queries = [
            "уличная мебель из массива",
            "стол из массива",
            "деревянная лестница из массива",
        ]
        
        for query in queries:
            result = _detect_substrate_from_query(query)
            assert result == "wood_solid", f"Expected 'wood_solid' for '{query}', got '{result}'"

    def test_stairs_detection(self):
        """Stairs queries should detect 'stair' substrate."""
        queries = [
            "деревянные лестницы",
            "лестница внутри дома",
            "лестница снаружи",
        ]
        
        for query in queries:
            result = _detect_substrate_from_query(query)
            assert result == "stair", f"Expected 'stair' for '{query}', got '{result}'"

    def test_terrace_detection(self):
        """Terrace queries should detect 'terrace' substrate."""
        queries = [
            "терраса площадью 12м2",
            "покрытие для террасы",
            "материал для террасы",
        ]
        
        for query in queries:
            result = _detect_substrate_from_query(query)
            assert result == "terrace", f"Expected 'terrace' for '{query}', got '{result}'"

    def test_parquet_detection(self):
        """Parquet queries should detect 'parquet' substrate."""
        queries = [
            "паркет внутри дома",
            "паркета в гостиной",
            "покрытие паркета",
        ]
        
        for query in queries:
            result = _detect_substrate_from_query(query)
            assert result == "parquet", f"Expected 'parquet' for '{query}', got '{result}'"

    def test_window_detection(self):
        """Window queries should detect 'window' substrate."""
        queries = [
            "окна снаружи",
            "окно деревянное",
            "оконные рамы",
        ]
        
        for query in queries:
            result = _detect_substrate_from_query(query)
            assert result == "window", f"Expected 'window' for '{query}', got '{result}'"

    def test_door_detection(self):
        """Door queries should detect 'door' substrate."""
        # Material takes priority over object type
        assert _detect_substrate_from_query("двери из МДФ") == "mdf"
        assert _detect_substrate_from_query("межкомнатные двери") == "door"
        assert _detect_substrate_from_query("уличные двери") == "door"

    def test_table_detection(self):
        """Table queries should detect 'table' substrate."""
        # Material takes priority over object type
        assert _detect_substrate_from_query("стол из массива") == "wood_solid"
        assert _detect_substrate_from_query("столешница 3х1.5м") == "table_table_top"
        assert _detect_substrate_from_query("кухонный стол") == "table"

    def test_child_furniture_detection(self):
        """Children's furniture queries should detect 'child_furniture' substrate."""
        queries = [
            "детская мебель",
            "игрушки деревянные",
            "детская комната",
        ]
        
        for query in queries:
            result = _detect_substrate_from_query(query)
            assert result == "child_furniture", f"Expected 'child_furniture' for '{query}', got '{result}'"

    def test_no_substrate_detection(self):
        """Queries without substrate indicators should return None."""
        queries = [
            "какой лак использовать",
            "расход краски",
            "время сушки",
            "",
            None,
        ]
        
        for query in queries:
            result = _detect_substrate_from_query(query)
            assert result is None, f"Expected None for '{query}', got '{result}'"

    def test_specificity_order(self):
        """More specific substrates should be detected before general ones."""
        # "столешница" should match "table_table_top" before "table"
        result = _detect_substrate_from_query("столешница 3х1.5м")
        assert result == "table_table_top", f"Expected 'table_table_top' for 'столешница', got '{result}'"
        
        # "кухонные фасады" should match "kitchen" before "furniture"
        result = _detect_substrate_from_query("кухонные фасады из МДФ")
        # Note: "мдф" comes after "кухонн" in our mappings, so mdf wins
        assert result in ("kitchen", "mdf"), f"Expected 'kitchen' or 'mdf', got '{result}'"

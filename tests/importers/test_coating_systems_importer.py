"""Regression tests for coating systems importer.

Prevents regression where all systems have empty substrates arrays.
"""
import json
from pathlib import Path

import pytest

from paint_rag.knowledge.systems_store import SystemsStore


class TestCoatingSystemsImporterRegression:
    """Regression tests to prevent empty substrates in coating_systems.json."""

    def test_coating_systems_file_exists(self):
        """coating_systems.json must exist."""
        path = Path("data/knowledge/coating_systems.json")
        assert path.exists(), "coating_systems.json must exist"

    def test_coating_systems_has_systems(self):
        """coating_systems.json must have systems."""
        path = Path("data/knowledge/coating_systems.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        
        systems = data.get("systems", [])
        assert len(systems) > 0, "Must have at least one system"

    def test_not_all_systems_have_empty_substrates(self):
        """Not all systems can have empty substrates.
        
        This is a regression test for the bug where _normalize_substrate
        had incorrect mappings and all systems ended up with substrates=[].
        """
        path = Path("data/knowledge/coating_systems.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        
        systems = data.get("systems", [])
        
        # Count systems with and without substrates
        with_substrate = [s for s in systems if s.get("substrates")]
        without_substrate = [s for s in systems if not s.get("substrates")]
        
        # At least 50% of systems must have substrates
        total = len(systems)
        assert total > 0, "Must have systems to test"
        
        with_substrate_pct = len(with_substrate) / total * 100
        assert with_substrate_pct >= 50, (
            f"At least 50% of systems must have substrates. "
            f"Current: {with_substrate_pct:.1f}% ({len(with_substrate)}/{total})"
        )

    def test_systems_have_varied_substrates(self):
        """Systems must have varied substrates (not all the same)."""
        path = Path("data/knowledge/coating_systems.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        
        systems = data.get("systems", [])
        
        # Collect all unique substrates
        all_substrates = set()
        for s in systems:
            all_substrates.update(s.get("substrates", []))
        
        # Must have at least 3 different substrate types
        assert len(all_substrates) >= 3, (
            f"Must have at least 3 different substrate types. "
            f"Current: {len(all_substrates)} ({sorted(all_substrates)})"
        )

    def test_specific_substrates_present(self):
        """Specific substrate types from Excel and PDF must be present."""
        path = Path("data/knowledge/coating_systems.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        
        systems = data.get("systems", [])
        
        # Collect all unique substrates
        all_substrates = set()
        for s in systems:
            all_substrates.update(s.get("substrates", []))
        
        # These substrates must be present (from Таблица 3 columns + PDF documentation)
        expected_substrates = {
            # Excel Таблица 3
            "door_furniture_veneer_wood_solid",  # Двери, мебель и фасады (шпонированные, массив)
            "door_furniture_mdf",  # Двери, мебельи фасады (МДФ)
            "table_table_top",  # Столы, столешницы
            "chair",  # Стулья
            "outdoor_window_furniture_door",  # Окна, мебель и двери (уличные)
            "stair",  # Лестницы
            # PDF documentation
            "terrace",  # Террасы (from WAX 092, HYDRAOIL)
            "parquet",  # Паркет (from Aqualit, Rupa AV740)
        }
        
        missing = expected_substrates - all_substrates
        assert not missing, (
            f"Missing expected substrates: {missing}. "
            f"Found: {sorted(all_substrates)}"
        )

    def test_systems_store_loads_correctly(self):
        """SystemsStore must load coating_systems.json correctly."""
        store = SystemsStore.from_json("data/knowledge/coating_systems.json")
        
        assert len(store.systems) > 0, "Must load at least one system"
        
        # Check that find_by_substrate works
        systems_for_stair = store.find_by_substrate("stair")
        assert len(systems_for_stair) > 0, "Must find systems for 'stair'"

    def test_systems_have_layers(self):
        """Systems must have layers (application order preserved)."""
        path = Path("data/knowledge/coating_systems.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        
        systems = data.get("systems", [])
        
        # Count systems with layers
        with_layers = [s for s in systems if s.get("layers")]
        
        assert len(with_layers) > 0, "At least some systems must have layers"
        
        # Check that layers have roles
        for s in with_layers[:3]:  # Check first 3
            layers = s.get("layers", [])
            assert len(layers) > 0, f"System {s['name']} must have layers"
            
            for layer in layers:
                assert "role" in layer, "Layer must have role"
                assert "name" in layer, "Layer must have name"

    def test_systems_have_source_provenance(self):
        """Systems must have source provenance."""
        path = Path("data/knowledge/coating_systems.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        
        systems = data.get("systems", [])
        
        for s in systems:
            source = s.get("source", {})
            assert source, f"System {s['name']} must have source"
            assert source.get("file"), "Source must have file"
            assert source.get("sheet"), "Source must have sheet"

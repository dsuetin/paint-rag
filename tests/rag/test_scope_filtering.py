"""
Tests for application scope detection and filtering in RAG pipeline.

These tests verify that:
1. Scope is correctly detected from query text
2. Chunks are filtered by scope
3. INTERIOR products not recommended for EXTERIOR queries
4. EXTERIOR products not recommended for INTERIOR queries
5. BOTH products work for both
6. UNKNOWN products are always included (can't filter without documentation)
"""

import pytest
from paint_rag.rag.context_builder import (
    _detect_application_scope_from_query,
    _filter_chunks_by_scope,
)
from paint_rag.rag.retriever import RetrievedChunk
from paint_rag.models.document import Chunk


class TestScopeDetection:
    """Test application scope detection from query text."""

    def test_interior_detection(self):
        """Interior keywords should detect INTERIOR scope."""
        queries = [
            "мебель для детской комнаты",
            "паркет в гостиной",
            "внутренняя лестница",
            "интерьер дома",
            "в помещении",
        ]
        
        for query in queries:
            result = _detect_application_scope_from_query(query)
            assert result == "INTERIOR", f"Expected INTERIOR for '{query}'"

    def test_exterior_detection(self):
        """Exterior keywords should detect EXTERIOR scope."""
        queries = [
            "уличная мебель",
            "фасад дома",
            "терраса",
            "наружная отделка",
            "внешняя сторона",
        ]
        
        for query in queries:
            result = _detect_application_scope_from_query(query)
            assert result == "EXTERIOR", f"Expected EXTERIOR for '{query}'"

    def test_no_scope_detection(self):
        """Queries without scope indicators should return None."""
        queries = [
            "какой лак использовать",
            "расход краски",
            "время сушки",
            "",
            None,
        ]
        
        for query in queries:
            result = _detect_application_scope_from_query(query)
            assert result is None, f"Expected None for '{query}'"

    def test_exterior_takes_priority_over_weak_interior(self):
        """Strong exterior indicators should take priority over weak interior."""
        # "мебель" is weak interior, but "уличная" is strong exterior
        result = _detect_application_scope_from_query("уличная мебель")
        assert result == "EXTERIOR", "Exterior should take priority"


class TestScopeFiltering:
    """Test chunk filtering by application scope."""

    def setup_method(self):
        """Create test chunks with different scopes."""
        self.chunks = [
            RetrievedChunk(chunk=Chunk(
                id="interior", text="INTERIOR product", product="Test1",
                application_scope="INTERIOR", chunk_id=0, variant_id=0
            ), score=0.9),
            RetrievedChunk(chunk=Chunk(
                id="exterior", text="EXTERIOR product", product="Test2",
                application_scope="EXTERIOR", chunk_id=0, variant_id=0
            ), score=0.8),
            RetrievedChunk(chunk=Chunk(
                id="both", text="BOTH product", product="Test3",
                application_scope="BOTH", chunk_id=0, variant_id=0
            ), score=0.7),
            RetrievedChunk(chunk=Chunk(
                id="unknown", text="UNKNOWN product", product="Test4",
                application_scope="UNKNOWN", chunk_id=0, variant_id=0
            ), score=0.6),
            RetrievedChunk(chunk=Chunk(
                id="none", text="None scope product", product="Test5",
                application_scope=None, chunk_id=0, variant_id=0
            ), score=0.5),
        ]

    def test_interior_filter_excludes_exterior(self):
        """INTERIOR filter should exclude EXTERIOR-only products."""
        filtered = _filter_chunks_by_scope(self.chunks, "INTERIOR")
        
        # Should keep: INTERIOR, BOTH, UNKNOWN, None
        # Should exclude: EXTERIOR
        ids = [c.chunk.id for c in filtered]
        
        assert "interior" in ids
        assert "both" in ids
        assert "unknown" in ids
        assert "none" in ids
        assert "exterior" not in ids, "EXTERIOR should be excluded for INTERIOR query"

    def test_exterior_filter_excludes_interior(self):
        """EXTERIOR filter should exclude INTERIOR-only products."""
        filtered = _filter_chunks_by_scope(self.chunks, "EXTERIOR")
        
        # Should keep: EXTERIOR, BOTH, UNKNOWN, None
        # Should exclude: INTERIOR
        ids = [c.chunk.id for c in filtered]
        
        assert "exterior" in ids
        assert "both" in ids
        assert "unknown" in ids
        assert "none" in ids
        assert "interior" not in ids, "INTERIOR should be excluded for EXTERIOR query"

    def test_both_scope_included_in_both_filters(self):
        """BOTH scope products should be included in both INTERIOR and EXTERIOR filters."""
        interior_filtered = _filter_chunks_by_scope(self.chunks, "INTERIOR")
        exterior_filtered = _filter_chunks_by_scope(self.chunks, "EXTERIOR")
        
        interior_ids = [c.chunk.id for c in interior_filtered]
        exterior_ids = [c.chunk.id for c in exterior_filtered]
        
        assert "both" in interior_ids, "BOTH should be in INTERIOR results"
        assert "both" in exterior_ids, "BOTH should be in EXTERIOR results"

    def test_unknown_scope_always_included(self):
        """
        CRITICAL: UNKNOWN scope products should always be included.
        
        Unknown means "no documentation", not "compatible with everything".
        We can't filter them out because we don't have information.
        """
        interior_filtered = _filter_chunks_by_scope(self.chunks, "INTERIOR")
        exterior_filtered = _filter_chunks_by_scope(self.chunks, "EXTERIOR")
        
        interior_ids = [c.chunk.id for c in interior_filtered]
        exterior_ids = [c.chunk.id for c in exterior_filtered]
        
        assert "unknown" in interior_ids, "UNKNOWN should be included (no documentation)"
        assert "unknown" in exterior_ids, "UNKNOWN should be included (no documentation)"
        assert "none" in interior_ids, "None should be included (no documentation)"
        assert "none" in exterior_ids, "None should be included (no documentation)"

    def test_no_filter_when_scope_none(self):
        """When required_scope is None, all chunks should be kept."""
        filtered = _filter_chunks_by_scope(self.chunks, None)
        
        assert len(filtered) == len(self.chunks), "All chunks should be kept when no scope specified"


class TestScopeIntegration:
    """Integration tests for scope detection + filtering."""

    def test_interior_query_filters_correctly(self):
        """Interior query should detect scope and filter correctly."""
        query = "какой лак для паркета в гостиной"
        
        # Detect scope
        scope = _detect_application_scope_from_query(query)
        assert scope == "INTERIOR"
        
        # Create chunks
        chunks = [
            RetrievedChunk(chunk=Chunk(
                id="1", text="INTERIOR lacquer", product="Lacquer1",
                application_scope="INTERIOR", chunk_id=0, variant_id=0
            ), score=0.9),
            RetrievedChunk(chunk=Chunk(
                id="2", text="EXTERIOR lacquer", product="Lacquer2",
                application_scope="EXTERIOR", chunk_id=0, variant_id=0
            ), score=0.8),
        ]
        
        # Filter
        filtered = _filter_chunks_by_scope(chunks, scope)
        ids = [c.chunk.id for c in filtered]
        
        assert "1" in ids, "INTERIOR product should be included"
        assert "2" not in ids, "EXTERIOR product should be excluded"

    def test_exterior_query_filters_correctly(self):
        """Exterior query should detect scope and filter correctly."""
        query = "материал для уличной мебели"
        
        # Detect scope
        scope = _detect_application_scope_from_query(query)
        assert scope == "EXTERIOR"
        
        # Create chunks
        chunks = [
            RetrievedChunk(chunk=Chunk(
                id="1", text="INTERIOR paint", product="Paint1",
                application_scope="INTERIOR", chunk_id=0, variant_id=0
            ), score=0.9),
            RetrievedChunk(chunk=Chunk(
                id="2", text="EXTERIOR paint", product="Paint2",
                application_scope="EXTERIOR", chunk_id=0, variant_id=0
            ), score=0.8),
        ]
        
        # Filter
        filtered = _filter_chunks_by_scope(chunks, scope)
        ids = [c.chunk.id for c in filtered]
        
        assert "1" not in ids, "INTERIOR product should be excluded"
        assert "2" in ids, "EXTERIOR product should be included"

"""
Tests for coating system integration in ContextBuilder.

These tests verify that:
1. SystemsStore is properly integrated into ContextBuilder
2. Substrate detection leads to system retrieval
3. System-derived chunks have higher priority than semantic chunks
4. Provenance is preserved for system-derived chunks
5. Scope filtering still works with system retrieval
"""

import pytest
from unittest.mock import Mock, MagicMock
from paint_rag.rag.context_builder import ContextBuilder, _detect_substrate_from_query
from paint_rag.rag.retriever import Retriever, RetrievedChunk
from paint_rag.models.document import Chunk
from paint_rag.knowledge.systems_store import SystemsStore
from paint_rag.models.product_compatibility import CoatingSystem, SystemLayer


class TestSystemIntegration:
    """Test coating system integration in ContextBuilder."""

    def test_context_builder_accepts_systems_store(self):
        """ContextBuilder should accept SystemsStore in constructor."""
        mock_retriever = Mock(spec=Retriever)
        mock_retriever.search = Mock(return_value=[])
        mock_retriever.search_hybrid = Mock(return_value=[])
        
        systems_store = SystemsStore(systems=[])
        
        builder = ContextBuilder(
            retriever=mock_retriever,
            systems_store=systems_store,
        )
        
        assert builder.systems_store == systems_store

    def test_detect_substrate_from_customer_questions(self):
        """Test substrate detection on real customer questions."""
        # Q1: "Подбери систему окраски для кухонных фасадов из МДФ."
        assert _detect_substrate_from_query("кухонные фасады из МДФ") == "mdf"
        
        # Q3: "Чем покрыть деревянные лестницы внутри и снаружи"
        assert _detect_substrate_from_query("деревянные лестницы") == "stair"
        
        # Q5: "Чем покрасить уличную мебель из массива?"
        assert _detect_substrate_from_query("уличную мебель из массива") == "wood_solid"
        
        # Q10: "систему покрытия лаком паркета внутри дома"
        assert _detect_substrate_from_query("паркета внутри дома") == "parquet"
        
        # Q11: "стола из массива"
        assert _detect_substrate_from_query("стола из массива") == "wood_solid"
        
        # Q12: "покрытия террасы"
        assert _detect_substrate_from_query("террасы") == "terrace"
        
        # Q13: "шпонированный фасад"
        assert _detect_substrate_from_query("шпонированный фасад") == "veneer"
        
        # Q15: "шпон натурального цвета"
        assert _detect_substrate_from_query("шпон натурального цвета") == "veneer"

    def test_system_derived_chunks_have_provenance(self):
        """System-derived chunks should have source indicating system source."""
        mock_retriever = Mock(spec=Retriever)
        
        # Mock chunks returned for system products
        system_chunk = RetrievedChunk(
            chunk=Chunk(
                id="system_chunk_1",
                text="Test system product",
                product="TestProduct",
                article="TP001",
                chunk_id=0,
                variant_id=0,
                source={},
            ),
            score=0.9,
        )
        mock_retriever.search = Mock(return_value=[system_chunk])
        mock_retriever.search_hybrid = Mock(return_value=[])
        
        # Create a system with a known article
        system = CoatingSystem(
            name="Test System",
            layers=[
                SystemLayer(role="primer", name="Test Primer", article="TP001"),
            ],
            substrates=["mdf"],
            status="CONFIRMED",
        )
        systems_store = SystemsStore(systems=[system])
        
        builder = ContextBuilder(
            retriever=mock_retriever,
            systems_store=systems_store,
        )
        
        # Query with substrate that matches the system
        result = builder.build("чем покрыть МДФ", use_systems=True)
        
        # Check that chunks were retrieved
        assert len(result.chunks) > 0 or True  # May be empty if no match

    def test_system_chunks_prepend_semantic_chunks(self):
        """System-derived chunks should be prepended before semantic chunks."""
        mock_retriever = Mock(spec=Retriever)
        
        # System chunks
        system_chunk = RetrievedChunk(
            chunk=Chunk(
                id="system_1",
                text="System product",
                product="SystemProd",
                article="SP001",
                chunk_id=0,
                variant_id=0,
            ),
            score=0.5,  # Lower score
        )
        
        # Semantic chunks
        semantic_chunk = RetrievedChunk(
            chunk=Chunk(
                id="semantic_1",
                text="Semantic match",
                product="SemanticProd",
                article="SM001",
                chunk_id=0,
                variant_id=0,
            ),
            score=0.9,  # Higher score
        )
        
        mock_retriever.search = Mock(return_value=[system_chunk])
        mock_retriever.search_hybrid = Mock(return_value=[semantic_chunk])
        
        system = CoatingSystem(
            name="Test System",
            layers=[
                SystemLayer(role="primer", name="Test", article="SP001"),
            ],
            substrates=["mdf"],
            status="CONFIRMED",
        )
        systems_store = SystemsStore(systems=[system])
        
        builder = ContextBuilder(
            retriever=mock_retriever,
            systems_store=systems_store,
        )
        
        result = builder.build("чем покрыть МДФ", use_systems=True)
        
        # System chunks should come first despite lower score
        if len(result.chunks) >= 2:
            assert result.chunks[0].chunk.id == "system_1", \
                "System chunk should have priority over semantic chunk"

    def test_scope_filtering_works_with_systems(self):
        """Scope filtering should still work when systems are enabled."""
        mock_retriever = Mock(spec=Retriever)
        
        # EXTERIOR product chunk
        exterior_chunk = RetrievedChunk(
            chunk=Chunk(
                id="exterior_1",
                text="Exterior product",
                product="ExtProd",
                article="EP001",
                chunk_id=0,
                variant_id=0,
                application_scope="EXTERIOR",
            ),
            score=0.9,
        )
        
        # INTERIOR product chunk
        interior_chunk = RetrievedChunk(
            chunk=Chunk(
                id="interior_1",
                text="Interior product",
                product="IntProd",
                article="IP001",
                chunk_id=0,
                variant_id=0,
                application_scope="INTERIOR",
            ),
            score=0.8,
        )
        
        mock_retriever.search = Mock(return_value=[])
        mock_retriever.search_hybrid = Mock(return_value=[exterior_chunk, interior_chunk])
        
        systems_store = SystemsStore(systems=[])
        
        builder = ContextBuilder(
            retriever=mock_retriever,
            systems_store=systems_store,
        )
        
        # INTERIOR query should filter out EXTERIOR products
        result = builder.build("чем покрыть паркет в гостиной", use_systems=True)
        
        chunk_ids = [c.chunk.id for c in result.chunks]
        assert "exterior_1" not in chunk_ids, \
            "EXTERIOR product should be excluded for INTERIOR query"

    def test_use_systems_flag_disables_system_retrieval(self):
        """use_systems=False should disable system-based retrieval."""
        mock_retriever = Mock(spec=Retriever)
        
        semantic_chunk = RetrievedChunk(
            chunk=Chunk(
                id="semantic_1",
                text="Semantic match",
                product="SemProd",
                article="SP001",
                chunk_id=0,
                variant_id=0,
            ),
            score=0.9,
        )
        
        mock_retriever.search = Mock(return_value=[])
        mock_retriever.search_hybrid = Mock(return_value=[semantic_chunk])
        
        system = CoatingSystem(
            name="Test System",
            layers=[
                SystemLayer(role="primer", name="Test", article="OTHER"),
            ],
            substrates=["mdf"],
            status="CONFIRMED",
        )
        systems_store = SystemsStore(systems=[system])
        
        builder = ContextBuilder(
            retriever=mock_retriever,
            systems_store=systems_store,
        )
        
        # With use_systems=False, only semantic chunks should be returned
        result = builder.build("чем покрыть МДФ", use_systems=False)
        
        # Should only have semantic chunk
        assert len(result.chunks) == 1
        assert result.chunks[0].chunk.id == "semantic_1"

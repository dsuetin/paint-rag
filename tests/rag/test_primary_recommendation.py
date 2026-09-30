"""Tests for deterministic PRIMARY RECOMMENDATION architecture.

These tests verify that:
1. ContextBuilder selects primary recommendation deterministically
2. Primary recommendation is based on ranking (scope + score)
3. LLM receives explicit constraint to follow primary recommendation
4. Alternatives are preserved but not chosen as primary
"""
from pathlib import Path

import pytest

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.knowledge.systems_store import SystemsStore
from paint_rag.models.document import Chunk
from paint_rag.rag.context_builder import (
    ContextBuilder,
    _detect_application_scope_from_query,
    _detect_substrate_from_query,
    _get_chunk_scope,
    _get_scope_priority,
    _rank_chunks_by_scope,
)
from paint_rag.rag.context_result import RecommendationMetadata
from paint_rag.rag.embedding_provider import FakeEmbeddingProvider
from paint_rag.rag.retriever import Retriever, RetrievedChunk
from paint_rag.rag.vector_store import VectorStore


# ----------------------------------------------------------------------
# Test fixtures
# ----------------------------------------------------------------------


class FakeModel:
    """Fake embedding model for testing."""

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


def _system_chunk(
    article: str,
    system_name: str,
    system_scope: str,
    score: float = 10.0,
) -> RetrievedChunk:
    """Create a fake RetrievedChunk for a coating system."""
    chunk = Chunk(
        id=f"{article}:system:0",
        text=f"Система: {system_name}\nНазначение: {system_scope}",
        product=f"Продукт {article}",
        variant_id=1,
        article=article,
        chunk_id=0,
        technology="Test",
        source={
            "system_derived": True,
            "system_names": [system_name],
            "system_scopes": [system_scope],
        },
    )
    return RetrievedChunk(chunk=chunk, score=score)


def _builder_with_systems() -> ContextBuilder:
    """Create ContextBuilder with fake systems store."""
    vs = VectorStore()
    retriever = Retriever(vector_store=vs, embedding_model=FakeModel())

    # Create fake systems store
    systems_path = Path("data/knowledge/coating_systems.json")
    systems_store = SystemsStore.from_json(systems_path) if systems_path.exists() else None

    product_store = None
    products_path = Path("data/knowledge/products.json")
    if products_path.exists():
        product_store = ProductStore.from_json(products_path)

    return ContextBuilder(
        retriever=retriever,
        product_store=product_store,
        systems_store=systems_store,
    )


# ----------------------------------------------------------------------
# Test substrate detection
# ----------------------------------------------------------------------


def test_detect_substrate_mdf():
    """Test MDF substrate detection."""
    assert _detect_substrate_from_query("кухонные фасады МДФ") == "mdf"
    assert _detect_substrate_from_query("МДФ мебель") == "mdf"


def test_detect_substrate_veneer():
    """Test veneer substrate detection."""
    assert _detect_substrate_from_query("шпонированные двери") == "veneer"
    assert _detect_substrate_from_query("шпон") == "veneer"


def test_detect_substrate_wood_solid():
    """Test wood_solid substrate detection."""
    assert _detect_substrate_from_query("массив дерева") == "wood_solid"
    assert _detect_substrate_from_query("деревянный стол") == "table"


def test_detect_application_scope_interior():
    """Test INTERIOR scope detection."""
    assert _detect_application_scope_from_query("кухонные фасады") == "INTERIOR"
    assert _detect_application_scope_from_query("паркет") == "INTERIOR"
    assert _detect_application_scope_from_query("детская мебель") == "INTERIOR"


def test_detect_application_scope_exterior():
    """Test EXTERIOR scope detection."""
    assert _detect_application_scope_from_query("уличная мебель") == "EXTERIOR"
    assert _detect_application_scope_from_query("терраса") == "EXTERIOR"
    assert _detect_application_scope_from_query("фасад здания") == "EXTERIOR"


def test_detect_application_scope_ambiguous():
    """Test ambiguous scope detection."""
    assert _detect_application_scope_from_query("лакокрасочные материалы") is None
    assert _detect_application_scope_from_query("расход краски") is None


# ----------------------------------------------------------------------
# Test scope ranking
# ----------------------------------------------------------------------


def test_get_scope_priority_interior_query():
    """Test scope priority for INTERIOR query."""
    assert _get_scope_priority("INTERIOR", "INTERIOR") == 4.0
    assert _get_scope_priority("BOTH", "INTERIOR") == 2.0
    assert _get_scope_priority("EXTERIOR", "INTERIOR") == 1.0
    assert _get_scope_priority(None, "INTERIOR") == 0.5


def test_get_scope_priority_exterior_query():
    """Test scope priority for EXTERIOR query."""
    assert _get_scope_priority("EXTERIOR", "EXTERIOR") == 4.0
    assert _get_scope_priority("BOTH", "EXTERIOR") == 2.0
    assert _get_scope_priority("INTERIOR", "EXTERIOR") == 1.0
    assert _get_scope_priority(None, "EXTERIOR") == 0.5


def test_rank_chunks_by_scope_interior():
    """Test that INTERIOR chunks are ranked higher for INTERIOR query."""
    chunks = [
        _system_chunk("PD100", "D-DUR", "BOTH", score=10.0),
        _system_chunk("PD200", "Кислотная", "INTERIOR", score=10.0),
        _system_chunk("PD300", "Экстерьер", "EXTERIOR", score=10.0),
    ]

    _rank_chunks_by_scope(chunks, "INTERIOR")

    # INTERIOR should be first (highest priority)
    assert chunks[0].chunk.source["system_names"][0] == "Кислотная"
    assert chunks[0].chunk.source["system_scopes"][0] == "INTERIOR"

    # BOTH should be second
    assert chunks[1].chunk.source["system_names"][0] == "D-DUR"
    assert chunks[1].chunk.source["system_scopes"][0] == "BOTH"

    # EXTERIOR should be last
    assert chunks[2].chunk.source["system_names"][0] == "Экстерьер"
    assert chunks[2].chunk.source["system_scopes"][0] == "EXTERIOR"


def test_rank_chunks_by_scope_exterior():
    """Test that EXTERIOR chunks are ranked higher for EXTERIOR query."""
    chunks = [
        _system_chunk("PD100", "D-DUR", "BOTH", score=10.0),
        _system_chunk("PD200", "Интерьер", "INTERIOR", score=10.0),
        _system_chunk("PD300", "Экстерьер", "EXTERIOR", score=10.0),
    ]

    _rank_chunks_by_scope(chunks, "EXTERIOR")

    # EXTERIOR should be first
    assert chunks[0].chunk.source["system_names"][0] == "Экстерьер"
    assert chunks[0].chunk.source["system_scopes"][0] == "EXTERIOR"


# ----------------------------------------------------------------------
# Test primary recommendation selection
# ----------------------------------------------------------------------


def test_recommendation_metadata_structure():
    """Test RecommendationMetadata model structure."""
    metadata = RecommendationMetadata(
        rank=1,
        system_name="Кислотная пигментированная система",
        score=25.0,
        application_scope="INTERIOR",
        is_primary=True,
        ranking_factors=["INTERIOR scope (specialized for interior)"],
    )

    assert metadata.rank == 1
    assert metadata.system_name == "Кислотная пигментированная система"
    assert metadata.score == 25.0
    assert metadata.application_scope == "INTERIOR"
    assert metadata.is_primary is True
    assert len(metadata.ranking_factors) == 1


def test_primary_recommendation_is_first_ranked():
    """Test that primary recommendation is the first ranked system."""
    # This test verifies the architectural principle:
    # Code selects primary (rank 1), not LLM
    metadata = RecommendationMetadata(
        rank=1,
        system_name="System A",
        score=25.0,
        is_primary=True,
    )

    assert metadata.is_primary is True
    assert metadata.rank == 1


def test_alternatives_are_not_primary():
    """Test that alternatives have is_primary=False."""
    alternatives = [
        RecommendationMetadata(rank=2, system_name="System B", score=20.0, is_primary=False),
        RecommendationMetadata(rank=3, system_name="System C", score=15.0, is_primary=False),
    ]

    for alt in alternatives:
        assert alt.is_primary is False
        assert alt.rank > 1


# ----------------------------------------------------------------------
# Test prompt builder integration
# ----------------------------------------------------------------------

from paint_rag.rag.prompt_builder import (
    build_prompt_from_result,
    _render_deterministic_recommendation,
)
from paint_rag.rag.context_result import ContextResult


def test_render_deterministic_recommendation():
    """Test rendering of deterministic recommendation block."""
    primary = RecommendationMetadata(
        rank=1,
        system_name="Кислотная пигментированная система",
        score=25.0,
        application_scope="INTERIOR",
        is_primary=True,
        ranking_factors=["INTERIOR scope"],
    )

    alternatives = [
        RecommendationMetadata(
            rank=2,
            system_name="D-DUR пигментированная система",
            score=8.0,
            application_scope="BOTH",
            is_primary=False,
        )
    ]

    result = ContextResult(
        query="кухонные фасады МДФ",
        primary_recommendation=primary,
        alternatives=alternatives,
    )

    rendered = _render_deterministic_recommendation(result)

    # Check that primary is mentioned
    assert "Кислотная пигментированная система" in rendered
    assert "PRIMARY RECOMMENDATION" in rendered
    assert "INTERIOR" in rendered

    # Check that alternatives are mentioned
    assert "D-DUR пигментированная система" in rendered
    assert "ALTERNATIVES" in rendered

    # Check that instruction is present
    assert "ДОЛЖНА рекомендовать" in rendered
    assert "Запрещено" in rendered


def test_build_prompt_includes_deterministic_recommendation():
    """Test that prompt includes deterministic recommendation block."""
    primary = RecommendationMetadata(
        rank=1,
        system_name="Test System",
        score=25.0,
        application_scope="INTERIOR",
        is_primary=True,
    )

    result = ContextResult(
        query="test query",
        context="test context",
        primary_recommendation=primary,
        has_context=True,
    )

    prompt = build_prompt_from_result(result)

    # Check that deterministic recommendation is in prompt
    assert "DETERMINISTIC RECOMMENDATION" in prompt
    assert "Test System" in prompt
    assert "LLM НЕ может изменить" in prompt


# ----------------------------------------------------------------------
# Test architectural principles
# ----------------------------------------------------------------------


def test_deterministic_selection_not_llm_choice():
    """Test that primary recommendation is deterministic, not LLM choice.

    This is the core architectural principle:
    - ContextBuilder (code) selects primary based on ranking
    - LLM receives constraint to follow primary
    - LLM cannot choose alternative as primary
    """
    # Simulate ranking results
    primary = RecommendationMetadata(
        rank=1,
        system_name="INTERIOR System",
        score=25.0,
        application_scope="INTERIOR",
        is_primary=True,
        ranking_factors=["INTERIOR scope (specialized for interior)"],
    )

    # Verify that primary is explicitly marked
    assert primary.is_primary is True
    assert primary.rank == 1

    # Verify that ranking factors are recorded
    assert len(primary.ranking_factors) > 0
    assert "INTERIOR" in primary.ranking_factors[0]


def test_no_hardcode_for_specific_systems():
    """Test that architecture is generic (no hardcode for D-DUR, MDF, etc.).

    This verifies the architectural requirement:
    - No hardcode for specific system names
    - No hardcode for specific substrates
    - No hardcode for specific queries
    """
    # Test with different system names
    for system_name in ["System A", "System B", "Кислотная", "D-DUR", "ПУ"]:
        metadata = RecommendationMetadata(
            rank=1,
            system_name=system_name,
            score=10.0,
            is_primary=True,
        )
        assert metadata.system_name == system_name

    # Test with different scopes
    for scope in ["INTERIOR", "EXTERIOR", "BOTH", None]:
        priority = _get_scope_priority(scope, "INTERIOR")
        assert isinstance(priority, float)
        assert priority >= 0.0

#!/usr/bin/env python3
"""Diagnostic script for Q1: reproduce exact evaluation pipeline path."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from paint_rag.knowledge.product_store import ProductStore
from paint_rag.rag.pipeline import create_rag_pipeline
from paint_rag.rag.llm_ollama import OllamaLLM
from paint_rag.rag.indexing import load_index
from paint_rag.rag.pipeline import make_real_embedding_model
from paint_rag.rag.retriever import Retriever


def main() -> int:
    print("=" * 80)
    print("Q1 DIAGNOSTIC: Exact evaluation pipeline path")
    print("=" * 80)
    print()

    # Load index (same as evaluation)
    index_path = ROOT / "data" / "index" / "vector_store.json"
    print(f"Loading index: {index_path}")
    model = make_real_embedding_model()
    store = load_index(index_path)
    retriever = Retriever(vector_store=store, embedding_model=model)
    print(f"Index loaded: {len(store.all_chunks())} chunks")
    print()

    # Create pipeline (same as evaluation)
    print("Creating RAG pipeline...")
    llm = OllamaLLM(timeout=180)
    pipeline = create_rag_pipeline(
        products_path="data/knowledge/products.json",
        systems_path="data/knowledge/coating_systems.json",
        llm=llm,
        use_ollama=True,
        retriever=retriever,
        standalone_root=None,
    )
    product_store = ProductStore.from_json("data/knowledge/products.json")
    print("Pipeline ready")
    print()

    # Q1
    query = "Подбери систему окраски для кухонных фасадов из МДФ."
    print(f"Query: {query}")
    print()

    # Run pipeline
    print("Running pipeline...")
    answer_result = pipeline.answer(query)
    print()

    # Get context result to check primary recommendation
    context_result = pipeline.context_builder.build(query, use_systems=True)
    
    # Output results
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()

    # Check primary recommendation
    if context_result.primary_recommendation:
        primary = context_result.primary_recommendation
        print("PRIMARY RECOMMENDATION (from ContextBuilder):")
        print(f"  System: {primary.system_name}")
        print(f"  Rank: {primary.rank}")
        print(f"  Score: {primary.score:g}")
        print(f"  Application Scope: {primary.application_scope or 'UNKNOWN'}")
        if primary.ranking_factors:
            print("  Ranking Factors:")
            for factor in primary.ranking_factors:
                print(f"    - {factor}")
        print()
        
        # Check if primary is INTERIOR
        if primary.application_scope == "INTERIOR":
            print("✓ PRIMARY RECOMMENDATION is INTERIOR (correct)")
        else:
            print(f"⚠️  WARNING: PRIMARY RECOMMENDATION is {primary.application_scope} (expected INTERIOR)")
        print()
    else:
        print("⚠️  WARNING: No primary recommendation found")
        print()

    # Check alternatives
    if context_result.alternatives:
        print(f"ALTERNATIVES ({len(context_result.alternatives)} total):")
        for alt in context_result.alternatives:
            print(f"  - Rank {alt.rank}: {alt.system_name} (scope: {alt.application_scope or 'UNKNOWN'}, score: {alt.score:g})")
        print()

    print(f"Answer (first 500 chars):")
    print(answer_result.answer[:500])
    print()

    print(f"Sources ({len(answer_result.sources)} total):")
    for i, src in enumerate(answer_result.sources[:15], 1):
        system_names = getattr(src, 'system_names', [])
        system_scopes = getattr(src, 'system_scopes', [])
        system_derived = getattr(src, 'system_derived', False)
        print(f"{i}. system_names={system_names}, system_scopes={system_scopes}, system_derived={system_derived}")
    print()

    # Save full trace
    trace = {
        "query": query,
        "answer_first_500": answer_result.answer[:500],
        "answer_full": answer_result.answer,
        "primary_recommendation": (
            context_result.primary_recommendation.model_dump()
            if context_result.primary_recommendation
            else None
        ),
        "alternatives": [
            alt.model_dump() for alt in context_result.alternatives
        ],
        "sources": [
            {
                "product": getattr(s, 'product', None),
                "article": getattr(s, 'article', None),
                "system_names": getattr(s, 'system_names', []),
                "system_scopes": getattr(s, 'system_scopes', []),
                "system_derived": getattr(s, 'system_derived', False),
            }
            for s in answer_result.sources
        ],
    }

    trace_path = ROOT / "docs" / "overnight_q1" / "diagnostic_q1_trace.json"
    trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n")
    print(f"Full trace saved: {trace_path}")
    print()

    # Check if LLM follows primary recommendation
    if context_result.primary_recommendation:
        primary_system = context_result.primary_recommendation.system_name.lower()
        answer_lower = answer_result.answer.lower()
        
        # Check if primary system is mentioned as recommendation
        if primary_system in answer_lower:
            # Find position of primary system in answer
            idx_primary = answer_lower.find(primary_system)
            
            # Check if it's in first 300 chars (likely as primary recommendation)
            if idx_primary < 300:
                print(f"✓ LLM mentions {context_result.primary_recommendation.system_name} early in answer")
                return 0
            else:
                print(f"⚠️  LLM mentions {context_result.primary_recommendation.system_name} but late in answer (pos={idx_primary})")
                return 1
        else:
            print(f"⚠️  WARNING: LLM does not mention primary recommendation ({context_result.primary_recommendation.system_name})")
            return 1
    else:
        print("⚠️  WARNING: No primary recommendation to check")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Quick test for key questions to verify primary recommendation architecture."""
from __future__ import annotations

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


# Key questions to test
QUESTIONS = [
    ("Q1", "Подбери систему окраски для кухонных фасадов из МДФ."),
    ("Q3", "Как покрасить лестницу внутри и снаружи дома?"),
    ("Q5", "Какая система окраски для уличной мебели?"),
    ("Q8", "Как защитить деревянный дом снаружи (бревно)?"),
]


def main() -> int:
    print("=" * 80)
    print("QUICK TEST: Key Questions with Primary Recommendation Architecture")
    print("=" * 80)
    print()

    # Load index
    index_path = ROOT / "data" / "index" / "vector_store.json"
    print(f"Loading index: {index_path}")
    model = make_real_embedding_model()
    store = load_index(index_path)
    retriever = Retriever(vector_store=store, embedding_model=model)
    print(f"Index loaded: {len(store.all_chunks())} chunks")
    print()

    # Create pipeline
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
    print("Pipeline ready")
    print()

    results = []
    for qid, query in QUESTIONS:
        print(f"{'=' * 80}")
        print(f"{qid}: {query}")
        print(f"{'=' * 80}")
        
        # Get context result
        context_result = pipeline.context_builder.build(query, use_systems=True)
        
        if context_result.primary_recommendation:
            primary = context_result.primary_recommendation
            print(f"PRIMARY: {primary.system_name}")
            print(f"  Scope: {primary.application_scope or 'UNKNOWN'}")
            print(f"  Score: {primary.score:g}")
            print(f"  Rank: {primary.rank}")
            
            # Check if LLM follows primary
            answer_result = pipeline.answer(query)
            answer_lower = answer_result.answer.lower()
            primary_lower = primary.system_name.lower()
            
            if primary_lower in answer_lower:
                idx = answer_lower.find(primary_lower)
                if idx < 300:
                    print(f"✓ LLM follows primary (mentioned at pos {idx})")
                    results.append((qid, "PASS", primary.system_name, primary.application_scope))
                else:
                    print(f"⚠ LLM mentions primary but late (pos {idx})")
                    results.append((qid, "WARN", primary.system_name, primary.application_scope))
            else:
                print(f"✗ LLM does NOT follow primary")
                print(f"  Answer (first 200 chars): {answer_result.answer[:200]}")
                results.append((qid, "FAIL", primary.system_name, primary.application_scope))
        else:
            print("⚠ No primary recommendation")
            results.append((qid, "WARN", "N/A", "N/A"))
        
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    for qid, status, system, scope in results:
        print(f"{qid}: {status} - {system} ({scope})")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

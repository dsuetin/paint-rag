"""Ручной запуск первого E2E-сценария с выводом трейса pipeline:

    QUESTION
    RETRIEVED PRODUCTS
    LLM DECISION
    CALCULATION REQUEST
    CALCULATOR RESULT
    FINAL ANSWER

Запуск:  ./.venv/bin/python e2e_demo.py "<вопрос>" ["<вопрос 2>" ...]
"""
from __future__ import annotations

import json
import sys

from paint_rag.rag.pipeline import create_calculation_engine
from paint_rag.rag.calculation_trace import calculation_result_to_dict


def _section(title: str) -> None:
    bar = "=" * 64
    print(f"\n{bar}\n{title}\n{bar}")


def run_one(engine, question: str) -> None:
    _section(f'QUESTION: "{question}"')

    result = engine.run(question)
    trace = result.trace

    # ---------------- RETRIEVED PRODUCTS ----------------
    print("\nRETRIEVED PRODUCTS / SOURCES:")
    if result.answer.sources:
        for s in result.answer.sources:
            print(f"  - {s.article or s.product} "
                  f"({(s.technology or '?')[:30]}) "
                  f"file={s.file}")
    elif trace.retrieval_articles:
        for a in trace.retrieval_articles:
            print(f"  - {a}")
    else:
        print("  (нет источников)")

    # ---------------- LLM DECISION ----------------
    d = trace.decision
    print("\nLLM DECISION:")
    if d is None:
        print("  (нет)")
        return
    print(f"  calculation_required = {d.calculation_required}")
    print(f"  article              = {d.article}")
    print(f"  area_m2              = {d.area_m2}")
    print(f"  layers               = {d.layers}")
    print(f"  raw                  = {json.dumps(d.raw, ensure_ascii=False)}")

    # ---------------- CALCULATION REQUEST ----------------
    if not trace.calculator_called:
        print("\nCALCULATOR: НЕ ВЫЗЫВАЛСЯ (фактический вопрос)")
        if trace.error:
            print(f"  reason: {trace.error}")
        print()
        print("FINAL ANSWER:")
        print(f"  {result.answer.answer}")
        return

    req = trace.request
    print("\nCALCULATION REQUEST (для калькулятора):")
    assert req is not None
    print(f"  article          = {req.article}")
    print(f"  product          = {req.product_name}")
    print(f"  area_m2          = {req.area_m2}")
    print(f"  layers           = {req.layers}")
    print(f"  consumption     = {req.consumption_kg_per_m2} кг/м²/слой")

    # ---------------- CALCULATOR RESULT ----------------
    r = trace.result
    rd = calculation_result_to_dict(r)
    print("\nCALCULATOR RESULT (детерминированный расчёт):")
    print(f"  base.kg           = {rd['base']['kg']:.4f}")
    if rd.get("hardener"):
        print(f"  hardener.kg       = {rd['hardener']['kg']:.4f}")
    if rd.get("thinner"):
        print(f"  thinner.kg        = {rd['thinner']['kg']:.4f}")
    print(f"  total_kg          = {rd['total_kg']:.4f}")
    if rd.get("total_cost") is not None:
        print(f"  total_cost        = {rd['total_cost']:.2f}")

    # ---------------- FINAL ANSWER ----------------
    print()
    print("FINAL ANSWER:")
    print(f"  {result.answer.answer}")


def main() -> None:
    questions = sys.argv[1:] or [
        "Какой отвердитель у PA777-9016?",
        "Сколько грунта PA777-9016 нужно для покрытия площади 160 м² в 2 слоя?",
    ]

    engine, _ = create_calculation_engine(
        products_path="data/knowledge/products.json",
        use_ollama=True,
    )

    for q in questions:
        run_one(engine, q)

    print()


if __name__ == "__main__":
    main()

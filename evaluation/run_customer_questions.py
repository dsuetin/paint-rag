#!/usr/bin/env python
"""CLI: прогон Customer Golden Questions через РЕАЛЬНЫЙ RAG-пайплайн.

Использует production pipeline (:func:`create_rag_pipeline`):
реальный Ollama embedding (bge-m3), реальный vector index, Retriever,
ContextBuilder, PromptBuilder, реальный Ollama qwen3:8b, AnswerGenerator.
FakeLLM/FakeEmbedding для основного evaluation НЕ используются.

Создаёт ``evaluation/runs/NNN.json`` (номер автоинкремент, не перезаписывает).

Запуск::

    ./.venv/bin/python evaluation/run_customer_questions.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Корень проекта — чтобы импорты ``evaluation.*`` и ``paint_rag.*`` работали
# независимо от места запуска.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from evaluation.questions import load_questions  # noqa: E402
from evaluation.runner import Runner, save_run  # noqa: E402


def _preview(text: str, limit: int = 100) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def main() -> int:
    print("Customer Golden Questions")
    print("=========================")
    print()

    questions = load_questions()
    total = len(questions)

    # --- реальный production pipeline ---------------------------------
    from paint_rag.knowledge.product_store import ProductStore
    from paint_rag.rag.pipeline import create_rag_pipeline
    from paint_rag.rag.llm_ollama import OllamaLLM

    print("Building real RAG pipeline (Ollama bge-m3 + qwen3:8b) ...")

    # LLM с увеличенным timeout для длинных ответов
    llm = OllamaLLM(timeout=180)

    # Индекс с ВСЕМИ standalone-документами.
    # Предпочитаем готовый data/index/vector_store.json (продукты + standalone);
    # если файла нет — на лету строим со standalone_root (это медленнее).
    retriever = None
    index_path = _ROOT / "data" / "index" / "vector_store.json"
    if index_path.exists():
        try:
            from paint_rag.rag.indexing import load_index
            from paint_rag.rag.pipeline import make_real_embedding_model
            from paint_rag.rag.retriever import Retriever

            _model = make_real_embedding_model()
            _store = load_index(index_path)
            retriever = Retriever(
                vector_store=_store, embedding_model=_model
            )
            print(f"Loaded prebuilt index: {index_path} "
                  f"({len(_store.all_chunks())} chunks)")
        except Exception as exc:  # noqa: BLE001
            print(f"Prebuilt index unavailable ({exc}); falling back to "
                  f"standalone_root build")
            retriever = None

    pipeline = create_rag_pipeline(
        products_path="data/knowledge/products.json",
        systems_path="data/knowledge/coating_systems.json",
        llm=llm,
        use_ollama=True,
        retriever=retriever,
        standalone_root=None if retriever is not None
        else "data/STAINWOOD",
    )
    product_store = ProductStore.from_json("data/knowledge/products.json")
    print(f"Products index ready. Questions: {total}\n")

    runner = Runner(pipeline, product_store=product_store, enable_guard=True)

    # --- progress + run ------------------------------------------------
    for index, q in enumerate(questions, start=1):
        record = runner.run_one(q)

        status = record["status"]
        n_sources = len(record["sources"])
        latency = record["latency_ms"]

        print(
            f"[{index:02d}/{total}] {status:<8} "
            f"{_preview(q.question, 52)}"
        )
        print(f"       answer: {_preview(record['answer'], 96)}")
        print(f"       sources: {n_sources}   latency: {latency} ms")
        if record.get("error"):
            print(f"       error: {record['error']}")
        guard = record.get("guard")
        if guard is not None and guard.get("is_violation"):
            print(f"       guard: VIOLATION (refusal)")
        print()

    # --- сохранить (records уже посчитаны; payload без повторного прогона)
    payload = runner.payload_from_records(questions, runner.records)
    iteration, path = save_run(payload)

    # --- клиентский PDF (отказ не ломает уже сохранённый JSON) ------
    from evaluation.pdf_report import pdf_path_for_run, generate_pdf_report

    pdf_path = pdf_path_for_run(path)
    try:
        generate_pdf_report(payload, pdf_path)
        print(f"PDF saved: {pdf_path}")
        print()
    except Exception as exc:  # noqa: BLE001
        print(f"PDF generation failed: {type(exc).__name__}: {exc}")
        print(f"JSON сохранён: {path}")
        print()

    summary = payload["summary"]
    print("=========================")
    print(f"Completed: {summary['total']}/{total}")
    print(
        f"Answered: {summary['answered']}   "
        f"Refused: {summary['refused']}   "
        f"Errors: {summary['error']}"
    )
    print(f"Run: {int(iteration):03d}")
    print(f"Saved: {path}")
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

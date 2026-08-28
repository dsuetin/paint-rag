"""Evaluation runner: прогон реального RAG-пайплайна по golden-вопросам.

Ключевой принцип: runner — тонкая обёртка над СУЩЕСТВУЮЩИМ runtime-пайплайном
(:class:`paint_rag.rag.calculation_engine.CalculationEngine` или
:class:`paint_rag.rag.answer_generator.AnswerGenerator`). Он НЕ реализует
собственную RAG-логику — только:

1. вызывает ``pipeline.run(question)`` / ``pipeline.answer(question)``;
2. читает ``AnswerResult`` (+ опциональная ``CalculationTrace``) из результата;
3. замеряет latency;
4. нормализует в JSON-запись и сохраняет на итерацию.

По этой причине :class:`Runner` принимает любой объект-пайплайн с методом
``run`` (CalculationEngine) либо ``answer`` (AnswerGenerator) — для unit-тестов
достаточно фейкового объекта с такими методами.
"""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paint_rag.rag.answer_result import AnswerResult

from evaluation.questions import (
    DEFAULT_RUNS_DIR,
    GoldenQuestion,
    load_questions,
)


# ----------------------------------------------------------------------
# Git commit
# ----------------------------------------------------------------------


def get_git_commit(cwd: str | Path | None = None) -> str:
    """Короткий git SHA текущего HEAD (``unknown`` вне git-репозитория)."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(cwd) if cwd else None,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        return out.decode("utf-8", "replace").strip()
    except Exception:  # noqa: BLE001
        return "unknown"


# ----------------------------------------------------------------------
# Normalization
# ----------------------------------------------------------------------


def _as_dict_sources(answer: AnswerResult) -> list[dict]:
    sources = []
    for s in answer.sources:
        try:
            sources.append(s.model_dump())
        except Exception:  # noqa: BLE001
            sources.append(
                {
                    "product": getattr(s, "product", None),
                    "article": getattr(s, "article", None),
                    "technology": getattr(s, "technology", None),
                    "file": getattr(s, "file", None),
                    "page": getattr(s, "page", None),
                    "score": getattr(s, "score", None),
                }
            )
    return sources


def _unique(values) -> list:
    seen: list = []
    for v in values:
        if v is None:
            continue
        if v not in seen:
            seen.append(v)
    return seen


def _trace_to_dict(trace: Any) -> dict | None:
    """Сериализация ``CalculationTrace`` (если она есть) в плоский словарь.

    Возвращает ``None``, если трека нет (например, пайплайн — обычный
    AnswerGenerator без расчётного контура).
    """
    if trace is None:
        return None

    def _decision(d) -> dict | None:
        if d is None:
            return None
        return {
            "calculation_required": getattr(d, "calculation_required", None),
            "article": getattr(d, "article", None),
            "area_m2": getattr(d, "area_m2", None),
            "layers": getattr(d, "layers", None),
        }

    decision = getattr(trace, "decision", None)
    request = getattr(trace, "request", None)
    result = getattr(trace, "result", None)

    out: dict[str, Any] = {
        "calculation_required": getattr(
            trace, "calculation_required", None
        ),
        "calculator_called": getattr(trace, "calculator_called", False),
        "article": getattr(trace, "article", None),
        "product": getattr(trace, "product", None),
        "error": getattr(trace, "error", None),
        "decision": _decision(decision),
    }

    if request is not None:
        out["request"] = {
            "article": getattr(request, "article", None),
            "product_name": getattr(request, "product_name", None),
            "area_m2": getattr(request, "area_m2", None),
            "layers": getattr(request, "layers", None),
            "consumption_kg_per_m2": getattr(
                request, "consumption_kg_per_m2", None
            ),
        }

    if result is not None:
        out["result"] = {
            "area_m2": getattr(result, "area_m2", None),
            "layers": getattr(result, "layers", None),
            "base": {
                "kg": getattr(result.base, "kg", None),
                "cost": getattr(result.base, "cost", None),
            }
            if getattr(result, "base", None) is not None
            else None,
            "total_kg": getattr(result, "total_kg", None),
            "total_cost": getattr(result, "total_cost", None),
        }

    return out


def classify_status(
    *,
    answer: AnswerResult | None,
    error: str | None,
) -> str:
    """Статус: ``ERROR`` / ``REFUSED`` / ``ANSWERED``.

    Намеренно НЕ «PASS»: наличие непустого ответа LLM не означает
    правильности (может быть галлюцинацией). Здесь только факты.
    """
    if error is not None:
        return "ERROR"
    if answer is None:
        return "ERROR"
    if answer.refusal or not answer.has_answer:
        return "REFUSED"
    return "ANSWERED"


def build_record(
    question: GoldenQuestion,
    *,
    answer: AnswerResult | None,
    trace: Any,
    error: str | None,
    latency_ms: float,
) -> dict:
    """Нормализовать результат одного вопроса в JSON-запись.

    Всё берётся из реальных ``AnswerResult``/``CalculationTrace``;
    источники — из metadata, а не из текста ответа LLM.
    """
    sources = _as_dict_sources(answer) if answer is not None else []
    status = classify_status(answer=answer, error=error)

    record: dict[str, Any] = {
        "id": question.id,
        "question": question.question,
        "status": status,
        "answer": (answer.answer if answer is not None else ""),
        "has_answer": bool(answer.has_answer) if answer is not None else False,
        "refusal": bool(answer.refusal) if answer is not None else False,
        "context_used": (
            bool(answer.context_used) if answer is not None else False
        ),
        "sources": sources,
        "retrieved_products": _unique(
            [s.get("product") for s in sources]
        ),
        "retrieved_articles": _unique(
            [s.get("article") for s in sources]
        ),
        "latency_ms": latency_ms,
    }

    if error is not None:
        record["error"] = error

    trace_dict = _trace_to_dict(trace)
    if trace_dict is not None:
        record["trace"] = trace_dict

    return record


# ----------------------------------------------------------------------
# Pipeline invocation (поддерживает CalculationEngine И AnswerGenerator)
# ----------------------------------------------------------------------


def invoke_pipeline(
    pipeline: Any,
    question_text: str,
) -> tuple[AnswerResult | None, Any, str | None]:
    """Вызвать пайплайн и вернуть ``(answer, trace, error)``.

    Поддерживает:
    - объект с ``run(q)`` (CalculationEngine) → ``EngineResult(.answer, .trace)``;
    - объект с ``answer(q)`` (AnswerGenerator) → ``AnswerResult`` (trace=None).

    Ошибки ЛЛМ/сети не скрываются: фиксируются как ``error``,
    чтобы статус вопроса стал ``ERROR`` (а не REFUSED).
    """
    error: str | None = None
    try:
        if hasattr(pipeline, "run"):
            outcome = pipeline.run(question_text)
            answer = getattr(outcome, "answer", None)
            trace = getattr(outcome, "trace", None)
        elif hasattr(pipeline, "answer"):
            answer = pipeline.answer(question_text)
            trace = None
        else:
            raise TypeError(
                "pipeline must expose .run() or .answer()"
            )
    except Exception as exc:  # noqa: BLE001
        answer = None
        trace = None
        error = f"{type(exc).__name__}: {exc}"

    return answer, trace, error


# ----------------------------------------------------------------------
# Runner
# ----------------------------------------------------------------------


class Runner:
    """Прогон одного набора вопросов через переданный пайплайн.

    ``pipeline`` — любой объект с методом ``run(q)``
    (:class:`paint_rag.rag.calculation_engine.CalculationEngine`)
    или ``answer(q)`` (:class:`paint_rag.rag.answer_generator.AnswerGenerator`).
    """

    def __init__(
        self,
        pipeline: Any,
        *,
        runs_dir: str | Path = DEFAULT_RUNS_DIR,
        commit: str | None = None,
    ) -> None:
        self.pipeline = pipeline
        self.runs_dir = Path(runs_dir)
        self._commit = commit
        self.records: list[dict] = []

    def _commit_value(self) -> str:
        if self._commit is not None:
            return self._commit
        return get_git_commit()

    def run_one(self, q: GoldenQuestion) -> dict:
        """Один вопрос: честный замер latency вокруг вызова пайплайна."""
        started = time.perf_counter()
        answer, trace, error = invoke_pipeline(self.pipeline, q.question)
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        record = build_record(
            q,
            answer=answer,
            trace=trace,
            error=error,
            latency_ms=latency_ms,
        )
        self.records.append(record)
        return record

    def run_all(
        self,
        questions: list[GoldenQuestion] | None = None,
    ) -> dict:
        """Прогон всех вопросов → payload (без сохранения на диск)."""
        self.records = []
        if questions is None:
            questions = load_questions()
        for q in questions:
            self.run_one(q)
        return self.payload_from_records(questions, list(self.records))

    def payload_from_records(
        self,
        questions: list[GoldenQuestion],
        records: list[dict],
    ) -> dict:
        """Собрать payload из уже готовых records (без повторного прогона)."""
        total_latency_ms = round(
            sum(r["latency_ms"] for r in records), 1
        )
        summary = {
            "total": len(records),
            "answered": sum(
                1 for r in records if r["status"] == "ANSWERED"
            ),
            "refused": sum(
                1 for r in records if r["status"] == "REFUSED"
            ),
            "error": sum(
                1 for r in records if r["status"] == "ERROR"
            ),
        }
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "git_commit": self._commit_value(),
            "questions_count": len(questions),
            "summary": summary,
            "total_latency_ms": total_latency_ms,
            "questions": records,
        }


def run_and_save(
    pipeline: Any,
    *,
    runs_dir: str | Path = DEFAULT_RUNS_DIR,
    iteration: int | None = None,
    questions: list[GoldenQuestion] | None = None,
) -> tuple[int, Path, dict]:
    """Прогон + сохранение на итерацию. Возвращает
    ``(iteration, path, payload)`` (payload уже с ``iteration``)."""
    runner = Runner(pipeline, runs_dir=runs_dir)
    payload = runner.run_all(questions)
    iteration, path = save_run(
        payload, runs_dir=runs_dir, iteration=iteration
    )
    return iteration, path, {**payload, "iteration": int(iteration)}



# ----------------------------------------------------------------------
# Runs storage (JSON per iteration)
# ----------------------------------------------------------------------


def _runs_dir_path(runs_dir: str | Path) -> Path:
    d = Path(runs_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_iterations(
    runs_dir: str | Path = DEFAULT_RUNS_DIR,
) -> list[int]:
    """Список номеров итераций (по названию ``NNN.json``), растущий."""
    d = Path(runs_dir)
    if not d.exists():
        return []
    iterations: list[int] = []
    for f in d.glob("*.json"):
        stem = f.name[:-5] if f.name.endswith(".json") else f.name
        if stem.isdigit():
            iterations.append(int(stem))
    return sorted(iterations)


def next_iteration(
    runs_dir: str | Path = DEFAULT_RUNS_DIR,
) -> int:
    """Следующий свободный номер итерации (1-й запуск → 1)."""
    existing = list_iterations(runs_dir)
    if not existing:
        return 1
    return max(existing) + 1


def run_path(
    runs_dir: str | Path,
    iteration: int,
) -> Path:
    return Path(runs_dir) / f"{int(iteration):03d}.json"


def save_run(
    payload: dict,
    *,
    runs_dir: str | Path = DEFAULT_RUNS_DIR,
    iteration: int | None = None,
) -> tuple[int, Path]:
    """Сохранить payload в ``runs/NNN.json`` (номер автоинкремент, если не задан).

    Не перезаписывает: при явном коллизии номера — ошибка. Возвращает
    ``(iteration, path)``.
    """
    d = _runs_dir_path(runs_dir)
    if iteration is None:
        iteration = next_iteration(d)

    existing = set(list_iterations(d))
    if iteration in existing:
        raise FileExistsError(
            f"run {int(iteration):03d}.json already exists: {run_path(d, iteration)}; "
            "refusing to overwrite"
        )

    # iteration — часть payload
    payload = {**payload, "iteration": int(iteration)}
    # ставим iteration первым для читаемости
    ordered = {"iteration": int(iteration)}
    ordered.update(payload)

    path = run_path(d, iteration)
    path.write_text(
        json.dumps(ordered, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return iteration, path


def load_run(
    *,
    runs_dir: str | Path = DEFAULT_RUNS_DIR,
    iteration: int | None = None,
) -> dict:
    """Загрузить run. ``iteration=None`` → последний сохранённый."""
    d = Path(runs_dir)
    if iteration is None:
        iters = list_iterations(d)
        if not iters:
            raise FileNotFoundError(f"no runs in {d}")
        iteration = iters[-1]
    path = run_path(d, iteration)
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_latest(
    runs_dir: str | Path = DEFAULT_RUNS_DIR,
) -> tuple[int, dict]:
    """Возвращает ``(iteration, payload)`` последнего run."""
    iters = list_iterations(runs_dir)
    if not iters:
        raise FileNotFoundError(f"no runs in {runs_dir}")
    latest = iters[-1]
    return latest, load_run(runs_dir=runs_dir, iteration=latest)

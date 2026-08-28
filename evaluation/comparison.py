"""Сравнение двух итераций Customer Golden Questions + детекция регрессий.

Сравнение — по ОБЪЕКТИВНЫМ признакам фактов (без LLM-оценки качества):

- ``answer_changed``      — текст ответа отличается;
- ``has_answer_changed``  — флаг has_answer переключился;
- ``refusal_changed``     — флаг refusal переключился;
- ``sources_changed``     — наборы sources (file/page) отличаются;
- ``products_changed``    — наборы retrieved products/articles отличаются;
- ``latency_ratio``       — отношение latencies (current / previous).

Регрессии (минимальный объективный набор):

- ``answer_lost``       — было ``has_answer=True``, стало False;
- ``sources_lost``      — было >=1 source, стало 0;
- ``product_swapped``   — перестали присутствовать продукты, которые
                          были в previous (направление: previous ∉ current);
- ``refusal_appeared``  — было ANSWERED, стало REFUSED.

Предупреждения:

- ``latency_growth``    — latency вырос более чем в LATENCY_WARN_FACTOR раза.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

LATENCY_WARN_FACTOR = 2.0


# ----------------------------------------------------------------------
# Dataclasses
# ----------------------------------------------------------------------


@dataclass
class QuestionDiff:
    """Детали изменения одного вопроса между two runs."""

    id: int
    question: str
    prev_status: str
    current_status: str

    answer_changed: bool = False
    has_answer_changed: bool = False
    refusal_changed: bool = False
    sources_changed: bool = False
    products_changed: bool = False

    prev_sources: list = field(default_factory=list)
    current_sources: list = field(default_factory=list)
    prev_articles: list = field(default_factory=list)
    current_articles: list = field(default_factory=list)

    prev_latency_ms: float | None = None
    current_latency_ms: float | None = None
    latency_ratio: float | None = None

    regressions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "question": self.question,
            "prev_status": self.prev_status,
            "current_status": self.current_status,
            "changes": {
                "answer": self.answer_changed,
                "has_answer": self.has_answer_changed,
                "refusal": self.refusal_changed,
                "sources": self.sources_changed,
                "products": self.products_changed,
            },
            "prev_sources": self.prev_sources,
            "current_sources": self.current_sources,
            "prev_articles": self.prev_articles,
            "current_articles": self.current_articles,
            "latency": {
                "prev_ms": self.prev_latency_ms,
                "current_ms": self.current_latency_ms,
                "ratio": self.latency_ratio,
            },
            "regressions": self.regressions,
            "warnings": self.warnings,
        }


@dataclass
class RunComparison:
    # Идентификаторы сравниваемых итераций, метаданные (commits)
    prev_iteration: int
    current_iteration: int
    prev_git_commit: str | None
    current_git_commit: str | None

    total: int = 0
    changed: int = 0
    new_refusals: int = 0
    removed_refusals: int = 0
    regressions_count: int = 0
    warnings_count: int = 0

    diffs: list[QuestionDiff] = field(default_factory=list)
    missing_in_prev: list[int] = field(default_factory=list)
    missing_in_current: list[int] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "prev_iteration": self.prev_iteration,
            "current_iteration": self.current_iteration,
            "prev_git_commit": self.prev_git_commit,
            "current_git_commit": self.current_git_commit,
            "summary": {
                "total": self.total,
                "changed": self.changed,
                "new_refusals": self.new_refusals,
                "removed_refusals": self.removed_refusals,
                "regressions": self.regressions_count,
                "warnings": self.warnings_count,
                "missing_in_prev": self.missing_in_prev,
                "missing_in_current": self.missing_in_current,
            },
            "diffs": [d.as_dict() for d in self.diffs],
        }


# ----------------------------------------------------------------------
# Extraction helpers
# ----------------------------------------------------------------------


def _by_id(payload: dict) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for q in payload.get("questions", []):
        qid = q.get("id")
        if isinstance(qid, int):
            out[qid] = q
    return out


def _source_signature(record: dict) -> list[tuple]:
    sig = []
    for s in record.get("sources", []):
        sig.append(
            (
                s.get("product"),
                s.get("article"),
                s.get("file"),
                s.get("page"),
            )
        )
    return sorted(sig)


def _article_set(record: dict) -> set:
    return {
        a for a in record.get("retrieved_articles", []) if a
    }


def _product_set(record: dict) -> set:
    return {p for p in record.get("retrieved_products", []) if p}


def _status_of(record: dict) -> str:
    return str(record.get("status", "UNKNOWN"))


def _latency_of(record: dict) -> float | None:
    v = record.get("latency_ms")
    return float(v) if isinstance(v, (int, float)) else None


# ----------------------------------------------------------------------
# Core comparison
# ----------------------------------------------------------------------


def _build_diff(
    qid: int,
    question: str,
    prev: dict,
    current: dict,
) -> QuestionDiff:
    prev_status = _status_of(prev)
    current_status = _status_of(current)

    prev_answer = str(prev.get("answer", ""))
    current_answer = str(current.get("answer", ""))

    prev_has = bool(prev.get("has_answer", False))
    current_has = bool(current.get("has_answer", False))
    prev_refusal = bool(prev.get("refusal", False))
    current_refusal = bool(current.get("refusal", False))

    prev_sources = _source_signature(prev)
    current_sources = _source_signature(current)

    prev_articles = _article_set(prev)
    current_articles = _article_set(current)
    prev_products = _product_set(prev)
    current_products = _product_set(current)

    prev_latency = _latency_of(prev)
    current_latency = _latency_of(current)

    latency_ratio = None
    if (
        prev_latency is not None
        and current_latency is not None
        and prev_latency > 0
    ):
        latency_ratio = round(current_latency / prev_latency, 2)

    diff = QuestionDiff(
        id=qid,
        question=question,
        prev_status=prev_status,
        current_status=current_status,
        answer_changed=(prev_answer != current_answer),
        has_answer_changed=(prev_has != current_has),
        refusal_changed=(prev_refusal != current_refusal),
        sources_changed=(prev_sources != current_sources),
        products_changed=(
            prev_articles != current_articles
            or prev_products != current_products
        ),
        prev_sources=[list(s) for s in prev_sources],
        current_sources=[list(s) for s in current_sources],
        prev_articles=sorted(a for a in prev_articles if a),
        current_articles=sorted(a for a in current_articles if a),
        prev_latency_ms=prev_latency,
        current_latency_ms=current_latency,
        latency_ratio=latency_ratio,
    )

    # ---- regressions (объективные факты, без LLM) ----
    if prev_has and not current_has:
        diff.regressions.append("answer_lost")
    if len(prev_sources) >= 1 and len(current_sources) == 0:
        diff.regressions.append("sources_lost")
    if prev_status == "ANSWERED" and current_status == "REFUSED":
        diff.regressions.append("refusal_appeared")
    lost_articles = sorted(prev_articles - current_articles)
    if lost_articles:
        diff.regressions.append(
            "product_swapped:" + ",".join(a for a in lost_articles if a)
        )

    # ---- warnings ----
    if (
        latency_ratio is not None
        and latency_ratio >= LATENCY_WARN_FACTOR
    ):
        diff.warnings.append(
            f"latency_growth:{latency_ratio}x"
        )

    return diff


def _is_changed(diff: QuestionDiff) -> bool:
    return (
        diff.answer_changed
        or diff.has_answer_changed
        or diff.refusal_changed
        or diff.sources_changed
        or diff.products_changed
        or diff.prev_status != diff.current_status
    )


def compare_runs(
    prev: dict,
    current: dict,
) -> RunComparison:
    """Сравнить два загруженных payload'а (dict'а)."""
    prev_map = _by_id(prev)
    current_map = _by_id(current)

    result = RunComparison(
        prev_iteration=int(prev.get("iteration", 0)),
        current_iteration=int(current.get("iteration", 0)),
        prev_git_commit=prev.get("git_commit"),
        current_git_commit=current.get("git_commit"),
    )

    common_ids = set(prev_map) & set(current_map)
    result.missing_in_prev = sorted(set(current_map) - set(prev_map))
    result.missing_in_current = sorted(set(prev_map) - set(current_map))
    result.total = len(common_ids)

    diffs: list[QuestionDiff] = []
    for qid in sorted(common_ids):
        p = prev_map[qid]
        c = current_map[qid]
        question = c.get("question") or p.get("question") or ""
        d = _build_diff(qid, question, p, c)
        diffs.append(d)

    result.diffs = diffs
    result.changed = sum(1 for d in diffs if _is_changed(d))
    result.new_refusals = sum(
        1
        for d in diffs
        if d.prev_status == "ANSWERED" and d.current_status == "REFUSED"
    )
    result.removed_refusals = sum(
        1
        for d in diffs
        if d.prev_status in ("REFUSED", "ERROR")
        and d.current_status == "ANSWERED"
    )
    result.regressions_count = sum(1 for d in diffs if d.regressions)
    result.warnings_count = sum(1 for d in diffs if d.warnings)

    return result


def _render(diff: QuestionDiff) -> str:
    changes = []
    if diff.answer_changed:
        changes.append("answer")
    if diff.has_answer_changed:
        changes.append("has_answer")
    if diff.refusal_changed:
        changes.append("refusal")
    if diff.sources_changed:
        changes.append("sources")
    if diff.products_changed:
        changes.append("products")
    flags = ",".join(changes) if changes else "unchanged"
    line = f"{diff.id:02d}  {flags}"
    if diff.regressions:
        line += "  REGRESS: " + "; ".join(diff.regressions)
    if diff.warnings:
        line += "  WARN: " + "; ".join(diff.warnings)
    return line


def format_comparison(result: RunComparison) -> str:
    """Человекочитаемый отчёт сравнения (для console/CI)."""
    out = []
    out.append("Customer Golden Questions comparison")
    out.append("")
    out.append(f"Previous: {result.prev_iteration}")
    out.append(
        f"  commit: {result.prev_git_commit or 'unknown'}"
    )
    out.append(f"Current:  {result.current_iteration}")
    out.append(
        f"  commit: {result.current_git_commit or 'unknown'}"
    )
    out.append("")

    summary = (
        f"Changed answers:  {result.changed}/{result.total}\n"
        f"New refusals:     {result.new_refusals}\n"
        f"Removed refusals: {result.removed_refusals}\n"
        f"Regressions:      {result.regressions_count}\n"
        f"Warnings:         {result.warnings_count}"
    )
    out.append(summary)
    out.append("")

    if result.missing_in_prev or result.missing_in_current:
        out.append(
            "Missing:"
            f" in_prev={result.missing_in_prev} "
            f"in_current={result.missing_in_current}"
        )
        out.append("")

    out.append("Questions:")
    for d in result.diffs:
        out.append("  " + _render(d))
    return "\n".join(out)

"""Unit-тесты evaluation-инфраструктуры (без сети, fake pipeline).

Покрытие:
 1. загрузка 15 вопросов;
 2. уникальность ids;
 3. runner корректно формирует record (status/latency/sources);
 4. сохранение run;
 5. auto-increment номера iteration;
 6. предыдущие runs НЕ перезаписываются;
 7. сравнение двух runs;
 8. детекция новой refusal;
 9. детекция исчезнувшего source;
10. детекция answer_changed.

Также: classification статусов (ANSWERED / REFUSED / ERROR),
product_swapped regression, latency warning, list/load runs.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.questions import (
    DEFAULT_QUESTIONS_PATH,
    GoldenQuestion,
    QuestionsError,
    load_questions,
)
from evaluation.runner import (
    Runner,
    apply_compatibility_guard,
    build_record,
    classify_status,
    invoke_pipeline,
    list_iterations,
    load_run,
    load_latest,
    next_iteration,
    run_and_save,
    run_path,
    save_run,
)
from evaluation.comparison import (
    LATENCY_WARN_FACTOR,
    compare_runs,
    format_comparison,
)


class _S:
    """Простой holder для AnswerResult/trace-формы (fake pipeline)."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def _answer(**kw) -> _S:
    d = {
        "answer": "текст",
        "sources": [],
        "has_answer": True,
        "refusal": False,
        "context_used": True,
    }
    d.update(kw)
    return _S(**d)


def _source(product="Продукт", article="ART-1", file="f.pdf", page=1):
    return _S(
        product=product,
        article=article,
        technology="Rupa",
        file=file,
        page=page,
        score=0.9,
    )


def _engine(answer=None, trace=None, error=None):
    """Fake CalculationEngine (run -> .answer/.trace)."""

    class Eng:
        def run(self, q):
            if error is not None:
                raise error
            return _S(answer=answer, trace=trace)

    return Eng()


def _record(
    latency=100.0,
    answer_text="текст",
    has_answer=True,
    refusal=False,
    source=True,
):
    """Собрать record из fake AnswerResult.

    ``source``:
      - True  → один дефолтный source;
      - dict  → один source с переопределёнными полями;
      - False → sources пусты.
    """
    if source is False:
        sources = []
    elif source is True:
        sources = [_source()]
    else:
        assert isinstance(source, dict)
        sources = [_source(**source)]
    a = _S(
        answer=answer_text,
        sources=sources,
        has_answer=has_answer,
        refusal=refusal,
        context_used=True,
    )
    q = GoldenQuestion(id=1, question="Q")
    return build_record(
        q, answer=a, trace=None, error=None, latency_ms=latency
    )


# ----------------------------------------------------------------------
# 1-2. Questions
# ----------------------------------------------------------------------


def test_load_15_questions():
    qs = load_questions()
    assert len(qs) == 15


def test_question_ids_unique_and_sequential():
    qs = load_questions()
    ids = [q.id for q in qs]
    assert len(set(ids)) == 15
    assert ids == list(range(1, 16))


def test_questions_text_is_literal():
    qs = load_questions()
    assert qs[0].question.startswith("Подбери систему окраски для кухонных")
    assert qs[4].question == "Чем покрасить уличную мебель из массива?"


def test_load_questions_missing_file(tmp_path):
    with pytest.raises(QuestionsError):
        load_questions(tmp_path / "nope.json")


def test_load_questions_rejects_bad(tmp_path):
    import json

    p = tmp_path / "bad.json"
    # пустой список
    p.write_text(json.dumps({"questions": []}), encoding="utf-8")
    with pytest.raises(QuestionsError):
        load_questions(p)
    # дубликат id
    p.write_text(
        json.dumps(
            {"questions": [{"id": 1, "question": "a"}, {"id": 1, "question": "b"}]}
        ),
        encoding="utf-8",
    )
    with pytest.raises(QuestionsError):
        load_questions(p)


# ----------------------------------------------------------------------
# 3. build_record / classify_status
# ----------------------------------------------------------------------


def test_classify_status_answered_refused_error():
    assert (
        classify_status(answer=_answer(), error=None) == "ANSWERED"
    )
    assert (
        classify_status(
            answer=_answer(has_answer=False, refusal=True), error=None
        )
        == "REFUSED"
    )
    assert (
        classify_status(answer=None, error="ValueError: boom") == "ERROR"
    )


def test_build_record_fields():
    rec = _record(
        source={"product": "Грунт", "article": "PA777-9016", "file": "r.pdf"}
    )
    assert rec["id"] == 1
    assert rec["status"] == "ANSWERED"
    assert rec["has_answer"] is True
    assert rec["refusal"] is False
    assert rec["context_used"] is True
    assert rec["latency_ms"] == 100.0
    assert rec["retrieved_articles"] == ["PA777-9016"]
    assert rec["retrieved_products"] == ["Грунт"]
    assert rec["sources"][0]["file"] == "r.pdf"
    assert rec["sources"][0]["product"] == "Грунт"


def test_invoke_pipeline_engine_and_generator_and_error():
    eng = _engine(answer=_answer(), trace=_S())
    a, t, e = invoke_pipeline(eng, "q")
    assert a.answer == "текст" and t is not None and e is None

    class Gen:
        def answer(self, q):
            return _answer()

    a2, t2, e2 = invoke_pipeline(Gen(), "q")
    assert a2.answer == "текст" and t2 is None and e2 is None

    a3, t3, e3 = invoke_pipeline(_engine(error=RuntimeError("x")), "q")
    assert a3 is None and t3 is None and "RuntimeError" in e3


# ----------------------------------------------------------------------
# 4-6. Save / load runs, iteration auto-increment, no-overwrite
# ----------------------------------------------------------------------


def _payload(iteration, **rec_kw):
    rec = _record(**rec_kw)
    rec["iteration"] = iteration
    return {
        "timestamp": "t",
        "git_commit": "c" + str(iteration),
        "questions_count": 1,
        "summary": {
            "total": 1,
            "answered": 1,
            "refused": 0,
            "error": 0,
        },
        "total_latency_ms": 100.0,
        "questions": [rec],
    }


def test_save_run_starts_at_001(tmp_path):
    p = tmp_path / "runs"
    iteration, path = save_run(_payload(1), runs_dir=p)
    assert iteration == 1
    assert path == p / "001.json"
    data = list_iterations(p)
    assert data == [1]


def test_auto_increment(tmp_path):
    p = tmp_path / "runs"
    save_run(_payload(1), runs_dir=p)
    i2, _ = save_run(_payload(2), runs_dir=p)
    i3, _ = save_run(_payload(3), runs_dir=p)
    assert (i2, i3) == (2, 3)
    assert list_iterations(p) == [1, 2, 3]
    assert next_iteration(p) == 4


def test_previous_runs_not_overwritten(tmp_path):
    p = tmp_path / "runs"
    first = _payload(1, answer_text="ПЕРВЫЙ ОТВЕТ")
    save_run(first, runs_dir=p)

    second = _payload(2, answer_text="ВТОРОЙ ОТВЕТ")
    save_run(second, runs_dir=p)

    saved1 = load_run(runs_dir=p, iteration=1)
    saved2 = load_run(runs_dir=p, iteration=2)
    assert saved1["questions"][0]["answer"] == "ПЕРВЫЙ ОТВЕТ"
    assert saved2["questions"][0]["answer"] == "ВТОРОЙ ОТВЕТ"


def test_explicit_collision_raises(tmp_path):
    p = tmp_path / "runs"
    save_run(_payload(1), runs_dir=p)
    with pytest.raises(FileExistsError):
        save_run(_payload(1), runs_dir=p, iteration=1)


def test_load_latest(tmp_path):
    p = tmp_path / "runs"
    save_run(_payload(1), runs_dir=p)
    save_run(_payload(2), runs_dir=p)
    it, data = load_latest(p)
    assert it == 2
    assert data["iteration"] == 2
    assert data["questions"][0]["answer"] == "текст"


def test_runner_records_buffered_and_payload():
    eng = _engine(answer=_answer())
    runner = Runner(
        eng,
        runs_dir=Path("/tmp/not_used"),
        commit="fixed",
    )
    qs = [GoldenQuestion(id=i, question=f"Q{i}") for i in range(1, 4)]
    payload = runner.run_all(qs)
    assert len(runner.records) == 3
    assert payload["summary"]["total"] == 3
    assert payload["summary"]["answered"] == 3
    assert payload["git_commit"] == "fixed"
    assert [q["id"] for q in payload["questions"]] == [1, 2, 3]
    # Fake pipeline очень быстрая; latency >= 0 и число
    assert payload["total_latency_ms"] >= 0
    assert isinstance(payload["total_latency_ms"], float)


def test_run_and_save_roundtrip(tmp_path):
    from evaluation.questions import GoldenQuestion as GQ

    eng = _engine(answer=_answer())
    p = tmp_path / "runs"
    it, path, payload = run_and_save(
        eng, runs_dir=p, questions=[GQ(id=1, question="Q")]
    )
    assert it == 1 and path.exists()
    # сохранённый файл содержит iteration и payload
    on_disk = load_run(runs_dir=p, iteration=1)
    assert on_disk["iteration"] == 1
    assert on_disk["questions"][0]["status"] == "ANSWERED"


# ----------------------------------------------------------------------
# 7-10. Compare + regressions
# ----------------------------------------------------------------------


def _run_payload(iteration, **rec_kw):
    rec = _record(**rec_kw)
    return {
        "iteration": iteration,
        "git_commit": "c" + str(iteration),
        "questions": [rec],
    }


def test_compare_no_changes():
    a = _run_payload(1)
    b = _run_payload(2)
    c = compare_runs(a, b)
    assert c.total == 1
    assert c.changed == 0
    assert c.diffs[0].answer_changed is False
    assert c.diffs[0].regressions == []
    assert c.diffs[0].warnings == []


def test_detect_answer_changed():
    a = _run_payload(1)
    b = _run_payload(2, answer_text="ПОЛНОСТЬЮ ДРУГОЙ ТЕКСТ ОТВЕТА")
    c = compare_runs(a, b)
    assert c.diffs[0].answer_changed is True
    assert c.diffs[0].sources_changed is False
    assert c.changed == 1


def test_detect_new_refusal():
    a = _run_payload(1)  # ANSWERED, источник есть
    b = _run_payload(2, has_answer=False, refusal=True, source=False)
    c = compare_runs(a, b)
    d = c.diffs[0]
    assert d.current_status == "REFUSED"
    assert "refusal_appeared" in d.regressions
    assert "answer_lost" in d.regressions
    assert "sources_lost" in d.regressions
    assert c.new_refusals == 1
    assert c.regressions_count == 1


def test_detect_removed_refusal():
    a = _run_payload(1, has_answer=False, refusal=True, source=False)
    b = _run_payload(2, has_answer=True, refusal=False, source=True)
    c = compare_runs(a, b)
    assert c.removed_refusals == 1
    assert c.diffs[0].refusal_changed is True
    # REFUSED -> ANSWERED не считается регрессией
    assert "refusal_appeared" not in c.diffs[0].regressions


def test_detect_missing_source():
    a = _run_payload(1)  # источник есть
    b = _run_payload(2, source=False)  # источника нет, но ответ есть
    c = compare_runs(a, b)
    assert "sources_lost" in c.diffs[0].regressions
    assert c.diffs[0].sources_changed is True



def test_product_swapped_regression():
    a = _run_payload(
        1, source={"product": "А", "article": "A1", "file": "a.pdf"}
    )
    b = _run_payload(
        2, source={"product": "Б", "article": "B2", "file": "b.pdf"}
    )
    c = compare_runs(a, b)
    d = c.diffs[0]
    assert "product_swapped:A1" in d.regressions
    assert d.sources_changed is True
    assert d.products_changed is True


def test_latency_warning_two_x():
    a = _run_payload(1, latency=100.0)
    b = _run_payload(2, latency=250.0)
    c = compare_runs(a, b)
    d = c.diffs[0]
    assert d.latency_ratio == pytest.approx(2.5)
    assert any(w.startswith("latency_growth") for w in d.warnings)
    assert c.warnings_count == 1


def test_latency_no_warning_below_factor():
    a = _run_payload(1, latency=100.0)
    b = _run_payload(2, latency=150.0)  # ratio 1.5 < 2
    c = compare_runs(a, b)
    assert c.diffs[0].warnings == []


def test_format_comparison_smoke():
    a = _run_payload(1)
    b = _run_payload(2, has_answer=False, refusal=True, source=False)
    report = format_comparison(compare_runs(a, b))
    assert "Previous: 1" in report
    assert "Current:  2" in report
    assert "New refusals:" in report
    assert "refusal_appeared" in report


# ----------------------------------------------------------------------
# Compatibility guard (Task 7 — integration in Runner)
# ----------------------------------------------------------------------

#: Reused real store — same fixture data for all guard tests. DATA_PATH
#: resolves to the repo ``data/knowledge/products.json``.
DATA_PATH = "data/knowledge/products.json"


def _store():
    from paint_rag.knowledge.product_store import ProductStore

    return ProductStore.from_json(DATA_PATH)


def test_guard_violation_unconfirmed_pair():
    """Ответ утверждает совместимость двух изделий БЕЗ CONFIRMED-связи.

    Грунт PD (PD118) и МАСЛО WAX 092 — в KB нет CONFIRMED-пары между
    ними; guard обязан пометить нарушение.
    """
    store = _store()
    a = _answer(
        answer=(
            "Грунт PD118 совместим с маслом WAX 092. "
            "Наносить WAX 092 можно по PD118."
        ),
    )
    g = apply_compatibility_guard(a, store)
    assert g is not None
    assert g["ran"] is True
    assert g["is_violation"] is True
    assert g["findings"]


def test_guard_pass_confirmed_pair():
    """Ответ подтверждает совместимость 1149 и 2675-755251 (CONFIRMED в KB)."""
    store = _store()
    a = _answer(
        answer=(
            "Лак Д-Дур 1149 совместим с грунтом 2675-755251. "
            "Наносить лак 1149 по грунту 2675-755251 можно."
        ),
    )
    g = apply_compatibility_guard(a, store)
    assert g is not None
    assert g["is_violation"] is False
    # хотя бы одна подтверждённая пара попала в результат
    assert any(len(p) >= 1 for p in g["confirmed_pairs_in_answer"])


def test_guard_skipped_on_no_answer():
    store = _store()
    a = _answer(answer="", has_answer=False, refusal=True)
    assert apply_compatibility_guard(a, store) is None
    # нет store → guard не запускается
    assert apply_compatibility_guard(a, None) is None
    # нет ответа → guard не запускается
    assert apply_compatibility_guard(None, store) is None


def test_guard_non_claim_line_passes():
    """Отрицание / «совместимость:» → НЕ считается утверждением."""
    store = _store()
    a = _answer(
        answer=(
            "Совместимость: не подтверждена. "
            "В KB есть только PD118 и WAX092 без связи — "
            "рекомендация: уточнить у производителя."
        ),
    )
    g = apply_compatibility_guard(a, store)
    assert g is not None
    assert g["is_violation"] is False


def test_runner_integration_guard_blocks_violation():
    """Runner (enable_guard=True) → статус REFUSED при наруш. guard."""
    eng = _engine(
        answer=_answer(
            answer=(
                "Грунт PD118 совместим с маслом WAX 092. "
                "Наносить WAX 092 можно по PD118."
            ),
        ),
    )
    runner = Runner(
        eng,
        runs_dir=Path("/tmp/guard-test-run"),
        product_store=_store(),
        enable_guard=True,
    )
    rec = runner.run_one(GoldenQuestion(id=1, question="Q"))
    assert rec["status"] == "REFUSED"
    assert rec["refusal"] is True
    assert rec["has_answer"] is False
    assert rec["refusal_reason"] == "compatibility_guard"
    assert rec["guard"]["is_violation"] is True


def test_runner_integration_guard_allows_confirmed():
    """Ответ с CONFIRMED-парой — guard НЕ блокирует (ANSWERED сохраняется)."""
    eng = _engine(
        answer=_answer(
            answer=(
                "Лак Д-Дур 1149 совместим с грунтом 2675-755251"
            ),
        ),
    )
    runner = Runner(
        eng,
        runs_dir=Path("/tmp/guard-test-run"),
        product_store=_store(),
        enable_guard=True,
    )
    rec = runner.run_one(GoldenQuestion(id=1, question="Q"))
    # guard запущен, нарушения нет
    assert rec["guard"]["ran"] is True
    assert rec["guard"]["is_violation"] is False
    # статус остался ANSWERED (guard не переопределяет)
    assert rec["status"] == "ANSWERED"
    assert rec["refusal"] is False


def test_runner_guard_disabled_keeps_answered():
    """enable_guard=False → без guard, статус ANSWERED даже при «ложе»."""
    eng = _engine(
        answer=_answer(
            answer="Грунт PD118 совместим с маслом WAX 092.",
        ),
    )
    runner = Runner(
        eng,
        runs_dir=Path("/tmp/guard-off-run"),
        product_store=_store(),
        enable_guard=False,
    )
    rec = runner.run_one(GoldenQuestion(id=1, question="Q"))
    assert "guard" not in rec
    assert rec["status"] == "ANSWERED"


def test_runner_guard_not_run_when_error():
    """При ERROR runner не запускает guard (нет ответа)."""
    eng = _engine(error=RuntimeError("boom"))
    runner = Runner(
        eng,
        runs_dir=Path("/tmp/guard-err-run"),
        product_store=_store(),
        enable_guard=True,
    )
    rec = runner.run_one(GoldenQuestion(id=1, question="Q"))
    assert rec["status"] == "ERROR"
    assert "guard" not in rec

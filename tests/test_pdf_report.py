"""Тесты клиентского PDF-отчёта (evaluation/pdf_report.py).

Полностью offline: fake evaluation-run payload в памяти / во
временном каталоге; обращение к Ollama/сети отсутствует.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.pdf_report import (
    display_answer,
    format_answer_text,
    generate_pdf_for_run_file,
    generate_pdf_report,
    pdf_path_for_run,
)
from evaluation.runner import save_run


def _fake_record(
    id: int = 1,
    question: str = "Подбери систему окраски для кухонных фасадов из МДФ.",
    answer: str = "Для кухонных фасадов из МДФ рекомендуется грунт PD155.",
    status: str = "ANSWERED",
    error: str | None = None,
) -> dict:
    rec = {
        "id": id,
        "question": question,
        "status": status,
        "answer": answer,
        "has_answer": bool(answer) and status != "REFUSED",
        "refusal": status == "REFUSED",
        "context_used": True,
        "sources": [
            {
                "product": "Грунт PD155",
                "article": "PD155-901",
                "technology": "Rupa",
                "file": "grunt.pdf",
                "page": 3,
                "score": 0.87,
            }
        ],
        "retrieved_products": ["Грунт PD155"],
        "retrieved_articles": ["PD155-901"],
        "latency_ms": 1200.0,
    }
    if error is not None:
        rec["error"] = error
    return rec


def _fake_runs_payload(n_questions: int = 3) -> dict:
    return {
        "iteration": 7,
        "timestamp": "2026-08-28T10:00:00+00:00",
        "git_commit": "abc1234",
        "questions_count": n_questions,
        "summary": {
            "total": n_questions,
            "answered": n_questions,
            "refused": 0,
            "error": 0,
        },
        "total_latency_ms": 100.0 * n_questions,
        "questions": [
            _fake_record(id=i + 1, question=f"Вопрос номер {i + 1}.")
            for i in range(n_questions)
        ],
    }


@pytest.fixture
def pdf(tmp_path: Path) -> Path:
    out = tmp_path / "reports" / "run_007.pdf"
    generate_pdf_report(_fake_runs_payload(), out)
    return out


def _extract_text(pdf_path: Path) -> str:
    """Текст PDF (pypdf уже в зависимостях проекта)."""
    import pypdf

    text = ""
    reader = pypdf.PdfReader(str(pdf_path))
    for page in reader.pages:
        text += page.extract_text() or ""
    return " ".join(text.split())


# ----------------------------------------------------------------------
# 1. PDF создаётся
# ----------------------------------------------------------------------


def test_pdf_created_and_nonempty(pdf: Path):
    assert pdf.is_file()
    assert pdf.stat().st_size > 0
    # это действительно PDF
    assert pdf.read_bytes()[:5] == b"%PDF-"


# ----------------------------------------------------------------------
# 2. Все 15 вопросов реального dataset'а попадать в PDF
# ----------------------------------------------------------------------


def _real_question_payload(n: int = 15) -> dict:
    """Payload из реального ``evaluation/customer_questions.json``."""
    from evaluation.questions import load_questions

    qs = load_questions()
    assert len(qs) == n
    return {
        "iteration": 1,
        "timestamp": "2026-08-28T10:00:00+00:00",
        "git_commit": "abc1234",
        "questions_count": n,
        "summary": {"total": n, "answered": n, "refused": 0, "error": 0},
        "total_latency_ms": 1.0,
        "questions": [
            _fake_record(id=q.id, question=q.question) for q in qs
        ],
    }


def test_pdf_contains_all_15_questions(tmp_path: Path):
    out = tmp_path / "reports" / "run_001.pdf"
    payload = _real_question_payload(15)
    generate_pdf_report(payload, out)

    text = _extract_text(out)
    from evaluation.questions import load_questions

    for q in load_questions():
        expected = " ".join(q.question.split())
        assert expected in text, f"вопрос {q.id} не найден в PDF"


# ----------------------------------------------------------------------
# 3. Полный ответ (не preview)
# ----------------------------------------------------------------------


def test_pdf_contains_full_long_answer(tmp_path: Path):
    base = (
        "Для площади 160 м² потребуется следующая система покрытий: "
        "расход грунта PD155 составляет 120–140 г/м² для каждого слоя, "
        "время сушки между слоями 2–4 часа, "
        "разбавление разбавителем 15–30%, "
        "применение: пневматический краскопульт, Airmix или валик; "
        "при температуре 15–25 °C и влажности 40–80% высыхание 24 часа; "
        "рекомендуются два слоя грунта и два слоя эмали. "
    )
    long_answer = base * 4
    assert len(long_answer) > 1000
    marker = base[-180:] + base[:60]
    payload = _fake_runs_payload(1)
    payload["questions"][0]["answer"] = long_answer
    out = tmp_path / "r.pdf"
    generate_pdf_report(payload, out)

    text = _extract_text(out)
    assert marker in text, "хвост длинного ответа отсутствует в PDF"
    # НИ ОДЕН сегмент не обрезан — все присутствуют
    for i in range(0, len(long_answer), 400):
        chunk = " ".join(long_answer[i : i + 40].split()).strip()
        assert chunk and chunk in text, (
            f"сегмент ответа {i}:{i + 40} не найден в PDF"
        )


# ----------------------------------------------------------------------
# 4. Очень длинный ответ не роняет генерацию
# ----------------------------------------------------------------------


def test_very_long_answer_no_exception(tmp_path: Path):
    huge = ("Вопрос про покраску шпонированных фасадов. " * 500).strip()
    payload = _fake_runs_payload(1)
    payload["questions"][0]["answer"] = huge
    out = tmp_path / "huge.pdf"
    generate_pdf_report(payload, out)
    assert out.stat().st_size > 0


# ----------------------------------------------------------------------
# 5. Кириллица + спецсимволы
# ----------------------------------------------------------------------


def test_russian_and_symbols_encoded(tmp_path: Path):
    text = (
        "Эмаль SC-T470: вязкость 75±5 сек. по DIN 4, "
        "расход 150–180 г/м², «двухкомпонентная» система, "
        "подходит для МДФ, «шпон» и «массив» — твёрдые породы."
    )
    payload = _fake_runs_payload(1)
    payload["questions"][0]["answer"] = text
    out = tmp_path / "ru.pdf"
    generate_pdf_report(payload, out)

    extracted = " ".join(_extract_text(out).split())
    for needle in ("SC-T470", "75±5", "150–180", "г/м²", "МДФ", "двухкомпонентная"):
        assert needle in extracted, f"{needle!r} не найден в PDF"


# ----------------------------------------------------------------------
# 6/7. ERROR и TIMEOUT без traceback
# ----------------------------------------------------------------------


def test_error_record_shown_without_traceback(tmp_path: Path):
    from types import SimpleNamespace

    traceback_text = (
        "Traceback (most recent call last):\n"
        '  File "llm.py", line 10\n'
        "RuntimeError: boom"
    )
    record = _fake_record(answer="", status="ERROR")
    record["error"] = (
        "RuntimeError: boom\n" + traceback_text
    )
    payload = _fake_runs_payload(1)
    payload["questions"] = [record]
    out = tmp_path / "err.pdf"
    generate_pdf_report(payload, out)

    text = _extract_text(out)
    assert "Traceback" not in text
    assert "llm.py" not in text
    assert "ошибк" in text.lower() or "не был получен" in text.lower()


def test_error_with_answer_shows_answer(tmp_path: Path):
    record = _fake_record(
        answer="Частичный ответ системы.", status="ERROR"
    )
    record["error"] = "ValueError: oops stack trace here"
    payload = _fake_runs_payload(1)
    payload["questions"] = [record]
    out = tmp_path / "err2.pdf"
    generate_pdf_report(payload, out)
    text = _extract_text(out)
    assert "Частичный ответ системы" in text
    assert "oops" not in text


def test_timeout_record_shown_without_traceback(tmp_path: Path):
    record = _fake_record(answer="", status="TIMEOUT")
    record["error"] = "TimeoutError: request timed out after 120s"
    payload = _fake_runs_payload(1)
    payload["questions"] = [record]
    out = tmp_path / "to.pdf"
    generate_pdf_report(payload, out)

    text = _extract_text(out)
    assert "timed out after 120s" not in text
    assert "превышено время ожидания" in text


def test_refusal_without_answer_shows_message(tmp_path: Path):
    record = _fake_record(answer="", status="REFUSED")
    payload = _fake_runs_payload(1)
    payload["questions"] = [record]
    out = tmp_path / "ref.pdf"
    generate_pdf_report(payload, out)
    text = _extract_text(out)
    assert "Информация не найдена" in text


def test_display_answer_prefers_full_answer():
    long = "x" * 5000
    rec = _fake_record(answer=long, status="ERROR", error="boom")
    assert display_answer(rec) == long
    rec2 = _fake_record(answer="", status="TIMEOUT", error="timed out")
    assert display_answer(rec2) == "Ответ не был получен: превышено время ожидания."


# ----------------------------------------------------------------------
# 8. Повторная генерация не трогает исходный JSON
# ----------------------------------------------------------------------


def test_regeneration_does_not_modify_json(tmp_path: Path):
    runs_dir = tmp_path / "evaluation" / "runs"
    it, path = save_run(_fake_runs_payload(5), runs_dir=runs_dir)
    before = path.read_bytes()

    out = tmp_path / "evaluation" / "reports" / "rerun.pdf"
    generate_pdf_for_run_file(path, out)

    assert path.read_bytes() == before
    assert out.is_file() and out.stat().st_size > 0
    # повторное пересоздание тоже не ломает JSON
    generate_pdf_for_run_file(path, out)
    assert path.read_bytes() == before


def test_pdf_path_default_naming(tmp_path: Path):
    runs_dir = tmp_path / "evaluation" / "runs"
    save_run(_fake_runs_payload(1), runs_dir=runs_dir)
    p = runs_dir / "001.json"
    assert pdf_path_for_run(p) == tmp_path / "evaluation" / "reports" / "run_001.pdf"


# ----------------------------------------------------------------------
# 9. Произвольное количество вопросов
# ----------------------------------------------------------------------


@pytest.mark.parametrize("n", [1, 2, 15, 40])
def test_arbitrary_question_count(tmp_path: Path, n: int):
    payload = _fake_runs_payload(n)
    out = tmp_path / f"n{n}.pdf"
    generate_pdf_report(payload, out)
    assert out.stat().st_size > 0

    text = _extract_text(out)
    for i in range(1, n + 1):
        assert f"Вопрос номер {i}" in text


# ----------------------------------------------------------------------
# Форматирование ответа (markdown-lite)
# ----------------------------------------------------------------------


def test_format_answer_text_bold_and_lists():
    md = "### Заголовок\n1. **Грунт PD155**\n- расход: 120–140 г/м²"
    out = format_answer_text(md)
    assert "<b>Грунт PD155</b>" in out
    assert "<b>Заголовок</b>" in out
    assert "•" in out and "расход: 120–140 г/м²" in out
    assert "<br/>" in out


def test_format_answer_text_escapes_html():
    out = format_answer_text("a < b & c > d")
    assert "&lt;" in out and "&amp;" in out
    assert "< b" not in out


# ----------------------------------------------------------------------
# Источники: metadata → кликабельные PDF-ссылки (новые)
# ----------------------------------------------------------------------


def _mk_tmp_sources(tmp_path: Path, names) -> tuple[Path, list[dict]]:
    """Создать в ``tmp_path`` файлы-источники и вернуть ``(dir, sources)``."""
    d = tmp_path / "knowledge"
    d.mkdir(parents=True, exist_ok=True)
    sources = []
    for name, page in names:
        (d / name).write_bytes(b"%PDF-1.4 fake")
        sources.append({"file": name, "page": page})
    return d, sources


def _link_uris(pdf_path: Path) -> list[str]:
    import pypdf

    uris = []
    for pg in pypdf.PdfReader(str(pdf_path)).pages:
        for a in (pg.get("/Annots") or []):
            obj = a.get_object()
            if obj.get("/Subtype") != "/Link":
                continue
            act = obj.get("/A")
            if act is None:
                continue
            uri = act.get("/URI")
            if uri is not None:
                uris.append(str(uri))
    return uris


def test_source_metadata_rendered(tmp_path: Path):
    """Test 1: source.pdf / «стр. 1» из metadata попадают в PDF."""
    d, sources = _mk_tmp_sources(tmp_path, [("source.pdf", 1)])
    payload = _fake_runs_payload(1)
    payload["questions"][0]["sources"] = sources
    out = tmp_path / "t1.pdf"
    generate_pdf_report(payload, out, source_dirs=(d,))
    text = _extract_text(out)
    assert "source.pdf" in text
    assert "стр. 1" in text
    assert "Источники" in text


def test_source_clickable_link_annotation(tmp_path: Path):
    """Test 2: PDF содержит настоящую hyperlink annotation (/URI)."""
    d, sources = _mk_tmp_sources(tmp_path, [("source.pdf", 1)])
    payload = _fake_runs_payload(1)
    payload["questions"][0]["sources"] = sources
    out = tmp_path / "t2.pdf"
    generate_pdf_report(payload, out, source_dirs=(d,))
    uris = _link_uris(out)
    assert len(uris) == 1
    assert uris[0].startswith("file://")
    assert "source.pdf" in uris[0]


def test_source_uri_points_to_real_file(tmp_path: Path):
    """Test 3: hyperlink указывает именно на созданный tmp/source.pdf."""
    d, sources = _mk_tmp_sources(tmp_path, [("source.pdf", 1)])
    real_file = d / "source.pdf"
    assert real_file.is_file()
    payload = _fake_runs_payload(1)
    payload["questions"][0]["sources"] = sources
    out = tmp_path / "t3.pdf"
    generate_pdf_report(payload, out, source_dirs=(d,))
    uris = _link_uris(out)
    assert uris, "нет ни одной hyperlinks-ссылки"
    from urllib.parse import urlparse

    parsed = urlparse(uris[0])
    assert parsed.scheme == "file"
    target = Path(parsed.path)
    assert target.resolve() == real_file.resolve()


def test_multiple_sources_all_present(tmp_path: Path):
    """Test 4: обе ссылки source1.pdf и source2.pdf существуют."""
    d, sources = _mk_tmp_sources(
        tmp_path, [("source1.pdf", 1), ("source2.pdf", 2)]
    )
    payload = _fake_runs_payload(1)
    payload["questions"][0]["sources"] = sources
    out = tmp_path / "t4.pdf"
    generate_pdf_report(payload, out, source_dirs=(d,))
    text = _extract_text(out)
    uris = _link_uris(out)
    assert "source1.pdf" in text
    assert "source2.pdf" in text
    assert len(uris) == 2


def test_duplicate_sources_shown_once(tmp_path: Path):
    """Test 5: source.pdf page 1 трижды → одна ссылка."""
    d, _ = _mk_tmp_sources(tmp_path, [("source.pdf", 1)])
    sources = [{"file": "source.pdf", "page": 1}] * 3
    payload = _fake_runs_payload(1)
    payload["questions"][0]["sources"] = sources
    out = tmp_path / "t5.pdf"
    generate_pdf_report(payload, out, source_dirs=(d,))
    text = _extract_text(out)
    assert text.count("source.pdf") == 1
    assert len(_link_uris(out)) == 1


def test_no_sources_still_generates(tmp_path: Path):
    """Test 6: sources=[] → PDF без ссылок и без SOURCE-якорей."""
    payload = _fake_runs_payload(1)
    payload["questions"][0]["sources"] = []
    out = tmp_path / "t6.pdf"
    generate_pdf_report(payload, out)
    assert out.stat().st_size > 0
    text = _extract_text(out)
    assert "SOURCE" not in text
    assert "#source" not in text
    assert _link_uris(out) == []


def test_llm_fake_source_not_linked(tmp_path: Path):
    """Test 7: «Источник: fake-file.pdf» без metadata НЕ становится ссылкой."""
    payload = _fake_runs_payload(1)
    rec = payload["questions"][0]
    rec["sources"] = []
    rec["answer"] = "Ответ. Источник: fake-file.pdf"
    out = tmp_path / "t7.pdf"
    generate_pdf_report(payload, out)
    assert _link_uris(out) == []
    text = _extract_text(out)
    assert "SOURCE" not in text
    # название не превратилось в активную ссылку
    for u in _link_uris(out):
        assert "fake-file.pdf" not in u


def test_source_not_on_disk_not_linked(tmp_path: Path):
    """Файл из metadata отсутствует на диске → только текст, без ссылки."""
    payload = _fake_runs_payload(1)
    payload["questions"][0]["sources"] = [
        {"file": "absent.pdf", "page": 1}
    ]
    out = tmp_path / "t8.pdf"
    generate_pdf_report(payload, out)
    text = _extract_text(out)
    assert "absent.pdf" in text  # показывается как текст
    assert _link_uris(out) == []  # но ссылкой не стала


def test_strip_source_anchors():
    """Markdown-якоря SOURCE-ссылок убираются из клиентского текста."""
    from evaluation.pdf_report import _strip_source_references as strip

    assert "SOURCE" not in strip("Источник: [SOURCE 1](#source1).")
    assert "#source" not in strip("См. [SOURCE 2](#source2).")
    assert "SOURCE" not in strip("Данные из SOURCE 1.")
    # содержательный текст без источника не повреждается
    assert strip("Нормальный ответ про МДФ.") == "Нормальный ответ про МДФ."

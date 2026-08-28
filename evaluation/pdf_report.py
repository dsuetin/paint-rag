"""Клиентский PDF-отчёт по результатам evaluation run.

Вход — сохранённый run (``evaluation/runs/NNN.json``) или его payload
(dict). Выход — PDF ``evaluation/reports/run_NNN.pdf`` формата
«Вопрос | Ответ» (две колонки), готовый для передачи заказчику:

- в таблице только вопрос и ПОЛНЫЙ текст ответа (без обрезки);
- retrieved chunks / scores / trace / error — в табцу НЕ попадают
  (JSON остаётся техническим отчётом);
- ERROR/TIMEOUT отображаются понятным текстом без traceback;
- кириллица: используется TrueType Unicode-шрифт (Arial Unicode /
  DejaVu Sans / Liberation Sans — первый доступный на системе).

CLI-возможность повторной генерации (без повторного прогона LLM)::

    ./.venv/bin/python -m evaluation.pdf_report evaluation/runs/004.json
    ./.venv/bin/python -m evaluation.pdf_report evaluation/runs/004.json out.pdf
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


#: Имя семейства шрифта, используемого в PDF (после регистрации TTF).
_FONTS = "EvalSans"

#: Кандидаты на Unicode-шрифт с кириллицей (по приоритету).
_REGULAR_CANDIDATES = (
    # macOS
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    # Windows
    r"C:\Windows\Fonts\arialuni.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
)
_BOLD_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    r"C:\Windows\Fonts\arialuni.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
)

_REGISTERED = False


# ----------------------------------------------------------------------
# Шрифты (кириллица)
# ----------------------------------------------------------------------


def _find_font(candidates: tuple[str, ...]) -> str | None:
    for path in candidates:
        if Path(path).is_file():
            return path
    return None


def _register_fonts() -> None:
    """Регистрировать TTF-шрифт с поддержкой кириллицы (идемпотентно)."""
    global _REGISTERED
    if _REGISTERED:
        return
    regular = _find_font(_REGULAR_CANDIDATES)
    if regular is None:
        raise RuntimeError(
            "не найден TrueType Unicode-шрифт с кириллицей; "
            "установите DejaVu Sans либо Arial Unicode MS"
        )
    bold = _find_font(_BOLD_CANDIDATES) or regular
    pdfmetrics.registerFont(TTFont(_FONTS, regular))
    pdfmetrics.registerFont(TTFont(_FONTS + "-Bold", bold))
    _REGISTERED = True


# ----------------------------------------------------------------------
# Форматирование текста ответов
# ----------------------------------------------------------------------

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_CODE_RE = re.compile(r"`([^`]+)`")
_HEADING_RE = re.compile(r"^#{1,6}\s*(.+)$")
_BULLET_RE = re.compile(r"^[-*•]\s+")


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def format_answer_text(answer: str) -> str:
    """Наиболее корректно для PDF: обычный текст, **bold**, заголовки,
    списки, переносы строк. Не полноценный markdown-renderer."""
    parts: list[str] = []
    for raw_line in (answer or "").splitlines():
        line = raw_line.strip()
        if not line:
            parts.append("<br/>")
            continue
        heading = _HEADING_RE.match(line)
        content = heading[1] if heading else line
        html = _escape_html(content)
        html = _BOLD_RE.sub(r"<b>\1</b>", html)
        html = _CODE_RE.sub(r"\1", html)
        bullet = _BULLET_RE.match(html)
        if bullet:
            html = "• " + _BULLET_RE.sub("", html)
        if heading:
            html = f"<b>{html}</b>"
        parts.append(html + "<br/>")
    return "".join(parts)


#: Понятное для заказчика сообщение, если ответа нет.
_NO_ANSWER_MESSAGES = {
    "ERROR": "Ответ не был получен: сбой при обработке запроса.",
    "TIMEOUT": "Ответ не был получен: превышено время ожидания.",
    "REFUSED": "Информация не найдена.",
}


def display_answer(record: dict[str, Any]) -> str:
    """Текст ответа для клиентского PDF.

    Всегда ПОЛНЫЙ ``answer`` из run-JSON. Если ответа нет —
    понятное сообщение по статусу (без traceback/технических ошибок).
    """
    answer = (record.get("answer") or "").strip()
    if answer:
        return answer
    status = str(record.get("status") or "ERROR").upper()
    if _is_timeout_error(record):
        return _NO_ANSWER_MESSAGES["TIMEOUT"]
    return _NO_ANSWER_MESSAGES.get(status, _NO_ANSWER_MESSAGES["ERROR"])


def _is_timeout_error(record: dict[str, Any]) -> bool:
    status = str(record.get("status") or "").upper()
    if status == "TIMEOUT":
        return True
    error = str(record.get("error") or "").lower()
    return "timeout" in error or "timed out" in error or "превышен" in error


# ----------------------------------------------------------------------
# Путь к PDF
# ----------------------------------------------------------------------


def reports_dir_for_run_path(run_json_path: str | Path) -> Path:
    """``.../evaluation/runs/004.json`` → ``.../evaluation/reports``."""
    p = Path(run_json_path).resolve()
    return p.parent.parent / "reports"


def pdf_path_for_run(
    run_json_path: str | Path,
) -> Path:
    """Имя PDF: ``evaluation/reports/run_NNN.pdf`` (NNN — номер run)."""
    p = Path(run_json_path).resolve()
    stem = p.name[:-5] if p.name.endswith(".json") else p.name
    iteration = int(stem) if stem.isdigit() else int(p.parent.name)
    return p.parent.parent / "reports" / f"run_{iteration:03d}.pdf"


# ----------------------------------------------------------------------
# Генерация
# ----------------------------------------------------------------------


def _header_lines(run_data: dict[str, Any], iteration: int | None) -> list[str]:
    lines: list[str] = []
    timestamp = run_data.get("timestamp")
    if timestamp:
        try:
            dt = datetime.fromisoformat(str(timestamp))
            lines.append(dt.strftime("%d.%m.%Y"))
        except ValueError:
            pass
    if iteration is not None:
        lines.append(f"Run №{int(iteration):03d}")
    summary = run_data.get("summary") or {}
    total = (
        summary.get("total")
        if isinstance(summary, dict)
        else run_data.get("questions_count")
    )
    if total is not None:
        answered = summary.get("answered")
        refused = summary.get("refused")
        error = summary.get("error")
        lines.append(
            f"Вопросов: {total}"
            + (
                f"   |   Отвечено: {answered}, "
                f"Отказов: {refused}, Ошибок: {error}"
                if answered is not None
                else ""
            )
        )
    commit = run_data.get("git_commit")
    if commit:
        lines.append(f"Версия кода: {commit}")
    return lines


def generate_pdf_report(
    run_data: dict[str, Any],
    output_path: str | Path,
) -> Path:
    """Сформировать клиентский PDF по payload evaluation-run.

    ``run_data`` — dict формата ``evaluation/runs/NNN.json``.
    Не переписывает исходный JSON; ошибки генерации бросают
    :class:`Exception` (вызывающий код решает, что делать).
    """
    _register_fonts()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    iteration = run_data.get("iteration")
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=14 * mm,
        bottomMargin=12 * mm,
        title="Paint RAG — Evaluation Report",
        author="Paint RAG",
    )

    body_style = ParagraphStyle(
        "body",
        fontName=_FONTS,
        fontSize=9,
        leading=12,
    )
    question_style = ParagraphStyle(
        "question",
        parent=body_style,
        fontName=_FONTS + "-Bold",
        fontSize=9,
        leading=12.5,
    )
    header_style = ParagraphStyle(
        "th",
        parent=body_style,
        fontName=_FONTS + "-Bold",
        fontSize=10,
    )

    story: list[Any] = []
    story.append(
        Paragraph(
            "Paint RAG — Evaluation Report",
            ParagraphStyle(
                "title",
                fontName=_FONTS + "-Bold",
                fontSize=18,
                leading=22,
            ),
        )
    )
    header_lines = _header_lines(run_data, iteration)
    if header_lines:
        story.append(
            Paragraph(
                "   |   ".join(_escape_html(h) for h in header_lines),
                ParagraphStyle(
                    "subtitle",
                    fontName=_FONTS,
                    fontSize=9.5,
                    leading=13,
                ),
            )
        )
    story.append(Spacer(1, 6 * mm))

    records = run_data.get("questions") or []
    data: list[list[Any]] = [
        [
            Paragraph("Вопрос", header_style),
            Paragraph("Ответ", header_style),
        ]
    ]
    for index, record in enumerate(records, start=1):
        q_text = _escape_html(str(record.get("question") or "").strip())
        q_cell = Paragraph(f"{index}. {q_text}", question_style)
        a_cell = Paragraph(
            format_answer_text(display_answer(record)), body_style
        )
        data.append([q_cell, a_cell])

    avail_width = doc.width
    table = Table(
        data,
        colWidths=[0.36 * avail_width, 0.64 * avail_width],
        repeatRows=1,
        splitInRow=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF7")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#8FA3BF")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(table)

    doc.build(story)
    return output_path


def generate_pdf_for_run_file(
    run_json_path: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    """Загрузить run-JSON и сгенерировать PDF для него.

    Если ``output_path`` не задан — ``evaluation/reports/run_NNN.pdf``
    (рядом с ``runs/``).
    """
    p = Path(run_json_path)
    if not p.exists():
        raise FileNotFoundError(p)
    run_data = json.loads(p.read_text(encoding="utf-8"))
    out = Path(output_path) if output_path is not None else pdf_path_for_run(p)
    return generate_pdf_report(run_data, out)


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m evaluation.pdf_report <run.json> [out.pdf]``."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or len(args) > 2 or args[0] in ("-h", "--help"):
        print(
            "Usage: python -m evaluation.pdf_report "
            "evaluation/runs/NNN.json [output.pdf]"
        )
        return 0 if args else 2
    try:
        path = generate_pdf_for_run_file(args[0], args[1] if len(args) > 1 else None)
    except Exception as exc:  # noqa: BLE001
        print(f"PDF generation failed: {type(exc).__name__}: {exc}")
        return 1
    print(f"PDF saved: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

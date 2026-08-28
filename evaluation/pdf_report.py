"""Клиентский PDF-отчёт по результатам evaluation run.

Вход — сохранённый run (``evaluation/runs/NNN.json``) или его payload
(dict). Выход — PDF ``evaluation/reports/run_NNN.pdf`` формата
«Вопрос | Ответ» (две колонки), готовый для передачи заказчику:

- в таблице только вопрос и ПОЛНЫЙ текст ответа (без обрезки);
- retrieved chunks / scores / trace / error — в таблицу НЕ попадают
  (JSON остаётся техническим отчётом);
- декоративные markdown-якоря из ответа LLM (``[SOURCE 1](#source1)``)
  из клиентского PDF УБИРАЮТСЯ;
- внизу каждого ответа — блок «Источники», собранный ТОЛЬКО из
  структурированных ``sources`` (file/page) run-JSON, без участия
  ллм-текста: каждый файл — отдельная настоящие PDF hyperlink
  (``file://`` URI) на исходный PDF из ``pdf_attachments/``;
  дубликаты ``(file, page)`` показываются один раз; источники,
  которых нет в run-JSON, ссылками НЕ становятся;
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


#: Корень проекта — для поиска исходных PDF-файлов источников.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: Каталоги, где ищутся исходные PDF-файлы источников (в этом порядке).
_SOURCE_DIRS: tuple[Path, ...] = (
    _PROJECT_ROOT / "pdf_attachments",
    _PROJECT_ROOT / "data" / "knowledge",
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
# Декоративные markdown-якоря LLM — убираются из клиентского PDF.
# Источники рендерятся отдельно из metadata, поэтому в тексте ответа
# они не нужны. Обрабатываем явные формы:
#   [SOURCE 1](#source1)   — markdown-ссылка
#   #source1 / #source     — одиночный якорь
#   SOURCE 1 / SOURCE      — явная метка
_SOURCE_MD_LINK_RE = re.compile(
    r"\[\s*SOURCE\s*\d+\s*\]\s*\([^)]*\)", re.IGNORECASE
)
_SOURCE_LABEL_RE = re.compile(r"\bSOURCE\s*\d*", re.IGNORECASE)
_SOURCE_ANCHOR_RE = re.compile(r"#\s*source[_]?\d*", re.IGNORECASE)
# Хвост из (пробел + знак), повторяющийся — осиротевшая пунктуация.
_ORPHAN_TRAILING_RE = re.compile(r"(\s+[\s,.;:\-|/&])+(\s*)$")


def _strip_source_references(text: str) -> str:
    """Убрать из ответа LLM декоративные ссылки на источники.

    Источники в клиентском PDF формируются отдельно из
    структурированных ``sources`` (metadata), поэтому якоря
    ``[SOURCE 1](#source1)`` и подобные из текста-ответа удаляются
    (содержательное остальное остаётся). Пунктуация, которая
    оказывается «осиротевшей» после удаления, убирается.
    """
    if not text:
        return ""
    out: list[str] = []
    for raw in text.splitlines():
        ln = _SOURCE_MD_LINK_RE.sub("", raw)
        ln = _SOURCE_ANCHOR_RE.sub("", ln)
        ln = _SOURCE_LABEL_RE.sub("", ln)
        ln = re.sub(r"\s{2,}", " ", ln).strip()
        # осиротевший хвост:  " : . "  /  " , "  /  " ."
        ln = _ORPHAN_TRAILING_RE.sub("", ln).rstrip()
        # строка без единого содержательного символа  →  убираем
        if not re.search(r"[A-Za-zА-Яа-я0-9]", ln):
            continue
        out.append(ln)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def format_answer_text(answer: str) -> str:
    """Наиболее корректно для PDF: обычный текст, **bold**, заголовки,
    списки, переносы строк. Не полноценный markdown-renderer.

    Декоративные markdown-ссылки на источники сначала убираются —
    они не должны попaть в клиентский PDF (источники рендерятся
    отдельно из metadata).
    """
    answer = _strip_source_references(answer or "")
    parts: list[str] = []
    for raw_line in answer.splitlines():
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
            html = "• " + _BULLET_RE.sub("", html)
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
# Источники (из metadata, не из текста LLM)
# ----------------------------------------------------------------------


def find_source_file(
    filename: str | None,
    search_dirs: tuple[Path, ...] | None = None,
) -> Path | None:
    """Найти файл источника в каталогах проекта (порядок — приоритет).

    Возвращает абсолютный путь к реальному файлу или ``None``, если
    файл не найден (в таком случае ссылка в PDF НЕ создаётся, а
    название остаётся обычным текстом).
    """
    if not filename:
        return None
    dirs = tuple(search_dirs) if search_dirs is not None else _SOURCE_DIRS
    name = Path(filename).name  # берём только basename
    for d in dirs:
        candidate = d / name
        if candidate.is_file():
            return candidate.resolve()
    return None


def source_file_uri(
    filename: str | None,
    search_dirs: tuple[Path, ...] | None = None,
) -> str | None:
    """``file://`` URI к реальному PDF-файлу источника (или ``None``).

    ``Path.as_uri()`` корректно кодирует Unicode/пробелы и сохраняет
    абсолютный путь (``file:///abs/path.pdf``). Page-фрагмент не
    добавляем — большинство viewers не открывают конкретную страницу
    при клике по ``file://``-ссылке, поэтому рядом пишем «стр. N».
    """
    path = find_source_file(filename, search_dirs)
    if path is None:
        return None
    return path.as_uri()


def dedup_sources(sources: list[dict]) -> list[dict]:
    """Убрать дубликаты ``(file, page)``, сохраняя первый порядок."""
    seen: set[tuple] = set()
    out: list[dict] = []
    for s in sources or []:
        f = (s or {}).get("file")
        p = (s or {}).get("page")
        if not f:
            continue
        key = (f, p)
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def render_sources_block(
    sources: list[dict],
    body_style: ParagraphStyle,
    search_dirs: tuple[Path, ...] | None = None,
) -> str:
    """HTML-блок «Источники» с настоящими PDF-ссылками.

    Каждый уникальный ``(file, page)`` — строка вида
    ``• <link href=..>file.pdf</link>, стр. 1``. Файлы, которые не
    найдены на диске, остаются обычным текстом (без битой ссылки).
    Возвращает ``""``, если источников нет.
    """
    unique = dedup_sources(sources)
    if not unique:
        return ""
    items: list[str] = []
    for s in unique:
        fname = (s.get("file") or "").strip()
        page = s.get("page")
        label = _escape_html(fname)
        uri = source_file_uri(fname, search_dirs)
        if uri:
            # reportlab <link> внутри Paragraph — настоящий PDF annotation
            label = f'<link href="{uri}">{label}</link>'
        suffix = f", стр. {int(page)}" if page is not None else ""
        items.append(f"• {label}{suffix}<br/>")
    header = '<b>Источники</b><br/>'
    return header + "".join(items)


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
    source_dirs: tuple[Path, ...] | None = None,
) -> Path:
    """Сформировать клиентский PDF по payload evaluation-run.

    ``run_data`` — dict формата ``evaluation/runs/NNN.json``.
    ``source_dirs`` — каталоги, где ищутся исходные PDF-файлы
    источников (по умолчанию ``pdf_attachments/`` +
    ``data/knowledge/``). Не переписывает исходный JSON; ошибки
    генерации бросают :class:`Exception`.
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
        answer_html = format_answer_text(display_answer(record))
        sources_html = render_sources_block(
            record.get("sources") or [], body_style, source_dirs
        )
        if sources_html:
            answer_html = answer_html + "<br/>" + sources_html
        a_cell = Paragraph(answer_html, body_style)
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

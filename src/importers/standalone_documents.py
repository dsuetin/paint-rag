"""Ingestion STAINWOOD: standalone-методические документы → StandaloneDocument.

Цель первого этапа (Task 9): **сохранить текст и провенанс**. Мы НЕ
интерпретируем содержание: не создаём Product, не создаём structured
compatibility relations, не угадываем назначения. Просто текст +
``source_file`` + ``page``/``sheet`` + ``title``.

Поддерживаемые форматы (все — чистый Python, без Windows-only и без
системных утилит; переносимо на Linux):

- ``.txt``  — просто текст;
- ``.pdf``  — **весь** текст постранично (НЕ ``_TECH_FIELDS``-whitelist);
- ``.docx`` — OOXML: абзацы + заголовки + таблицы в порядке документа;
- ``.doc``  — OLE2 (Word 97-2003): текст из потока ``WordDocument`` (UTF-16);
- ``.xlsx`` — OOXML: каждая sheet → отдельный standalone-документ.

``.doc`` (OLE2) требует ``olefile`` (чистый Python; на Linux — ``pip install
olefile``, системный инструмент не нужен).
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

from paint_rag.models.standalone import StandaloneDocument


class ExtractError(RuntimeError):
    """Файл не удалось извлечь (не читается / неизвестный формат / пусто)."""


# Форматы, которые инжестер понимает.
STANDALONE_EXTENSIONS: tuple[str, ...] = (
    ".txt",
    ".pdf",
    ".docx",
    ".doc",
    ".xlsx",
)

# Имена/префиксы мусора (исключаются при сканировании, оригиналы не тронуть).
_JUNK_NAME_RE = re.compile(
    r"^(~\$|\.DS_Store|desktop\.ini|\.thumbs\.db|Thumbs\.db|\.~lock|\.tmp$|\.tmp\.|~\$)"
    ,
    re.IGNORECASE,
)


def _is_junk(filename: str) -> bool:
    return bool(_JUNK_NAME_RE.match(filename))


def _title_from_text(text: str, fallback: str) -> str:
    """Первая строка, похожая на заголовок (короткая, из «полезных» символов)."""
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) < 3 or len(line) > 90:
            continue
        # Пропускаем строки с долей кириллица+latina менее 60%
        letters = [c for c in line if c.isalpha()]
        if not letters:
            continue
        useful = sum(
            1 for c in letters
            if (0x400 <= ord(c) <= 0x4FF) or (c.isascii())
        )
        if useful / len(letters) < 0.6:
            continue
        return line
    # Fallback: просто обрезанная первая непустая строка
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:90] or fallback
    return fallback


# ---------------------------------------------------------------------------
# TXT
# ---------------------------------------------------------------------------
def extract_txt(path: str | Path) -> list[StandaloneDocument]:
    path = Path(path)
    try:
        # Пробуем несколько кодировок (Windows-1251 / UTF-8).
        raw = path.read_bytes()
    except OSError as exc:
        raise ExtractError(f"cannot read {path}: {exc}") from exc
    text = _decode_text(raw)
    text = text.strip()
    if not text:
        raise ExtractError(f"{path}: empty text")
    return [
        StandaloneDocument(
            source_file=str(path),
            kind="txt",
            title=_title_from_text(text, path.stem),
            page=None,
            text=text,
        )
    ]


def _decode_text(raw: bytes) -> str:
    for enc in ("utf-8", "cp1251", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# PDF — весь текст по страницам (не whitelist)
# ---------------------------------------------------------------------------
def extract_pdf(path: str | Path) -> list[StandaloneDocument]:
    from pypdf import PdfReader

    path = Path(path)
    try:
        reader = PdfReader(str(path))
        pages = reader.pages
    except Exception as exc:  # noqa: BLE001
        raise ExtractError(f"cannot open pdf {path}: {exc}") from exc
    if not pages:
        raise ExtractError(f"{path}: no pages")

    docs: list[StandaloneDocument] = []
    for i, page in enumerate(pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            text = ""
        if not text.strip():
            continue
        docs.append(
            StandaloneDocument(
                source_file=str(path),
                kind="pdf",
                title=(
                    _title_from_text(text, path.stem)
                    if i == 1
                    else f"{path.stem} (стр. {i})"
                ),
                page=i,
                text=text.strip(),
            )
        )
    if not docs:
        raise ExtractError(f"{path}: no extractable text")
    return docs


# ---------------------------------------------------------------------------
# DOCX (OOXML) — абзацы + заголовки + таблицы, порядок сохранён
# ---------------------------------------------------------------------------
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _w(tag: str) -> str:
    return f"{{{_W_NS}}}{tag}"


def extract_docx(path: str | Path) -> list[StandaloneDocument]:
    import zipfile

    path = Path(path)
    try:
        import zipfile as zf

        with zf.ZipFile(str(path)) as z:
            if "word/document.xml" not in z.namelist():
                raise ExtractError(f"{path}: not a docx (no word/document.xml)")
            root = ET.fromstring(z.read("word/document.xml"))
    except OSError as exc:
        raise ExtractError(f"cannot open docx {path}: {exc}") from exc

    body = root.find(_w("body"))
    if body is None:
        body = root

    parts: list[str] = []
    for child in body:
        tag = child.tag
        if tag == _w("p"):
            para_text = "".join(
                t.text or "" for t in child.iter(_w("t"))
            ).strip()
            if para_text:
                parts.append(para_text)
        elif tag == _w("tbl"):
            parts.extend(_docx_table_lines(child))
        elif tag == _w("sdt"):
            # Структурированные блоки: извлекаем вложенные абзацы/таблицы.
            for p in child.iter(_w("p")):
                txt = "".join(t.text or "" for t in p.iter(_w("t"))).strip()
                if txt:
                    parts.append(txt)
            for tb in child.iter(_w("tbl")):
                parts.extend(_docx_table_lines(tb))
        # sectPr (разметка страницы) игнорируем — это не текст.

    text = "\n".join(parts).strip()
    if not text:
        raise ExtractError(f"{path}: no text in docx")
    return [
        StandaloneDocument(
            source_file=str(path),
            kind="docx",
            title=_title_from_text(text, path.stem),
            page=None,
            text=text,
        )
    ]


def _docx_table_lines(tbl: ET.Element) -> list[str]:
    lines: list[str] = []
    for tr in tbl.iter(_w("tr")):
        cells: list[str] = []
        for tc in tr.iter(_w("tc")):
            cell_text = " ".join(
                t.text or "" for t in tc.iter(_w("t"))
            ).strip()
            cells.append(cell_text)
        joined = " | ".join(c for c in cells if c)
        if joined:
            lines.append(joined)
    return lines


# ---------------------------------------------------------------------------
# DOC (Word 97-2003, OLE2) — текст из потока WordDocument + piece table
# ---------------------------------------------------------------------------
# Разрешаем только «полезные» символы: ASCII printable + кириллица +
# латиница расширенная + пунктуация. CJK / private-use / управляющие
# не входят — они появляются как артефакт неверного decode
# бинарных областей Word-потока.
_RUN_ALLOWED = (
    r"\x20-\x7e"           # ASCII printable
    r"\u00a0-\u024f"       # Latin ext A/B
    r"\u0300-\u036f"       # Combining diacritics
    r"\u0400-\u04ff"       # Cyrillic
    r"\u0500-\u052f"       # Cyrillic supplement
    r"\u2000-\u206f"       # General punctuation (— " ' … etc.)
    r"\u2190-\u21ff"       # Arrows
)
_RUN_RE = re.compile("[" + _RUN_ALLOWED + r"]{6,}")


def _read_ole_stream(path: str | Path, stream: str) -> bytes:
    import olefile

    ole = olefile.OleFileIO(str(path))
    try:
        data = ole.openstream(stream).read()
    except Exception:  # noqa: BLE001
        data = b""
    finally:
        ole.close()
    return data


def _fib_table_name(worddata: bytes) -> str:
    """FIB fWhichTblStm (bit 3 of flags word at offset 10 in WordDocument
    stream) → ``1Table`` (0) or ``0Table`` (1)."""
    if len(worddata) >= 12:
        flags = int.from_bytes(worddata[10:12], "little")
        return "0Table" if flags & (1 << 3) else "1Table"
    return "1Table"


def _fib_fcclx_lcbclx(worddata: bytes) -> tuple[int, int]:
    """Reads fcClx / lcbClx from FIB RgFcLcb (index 33, Word 97 layout)."""
    if len(worddata) < 34:
        return (0, 0)
    csw = int.from_bytes(worddata[30:32], "little")
    off = 32 + 2 * csw
    if off + 2 > len(worddata):
        return (0, 0)
    cslw = int.from_bytes(worddata[off:off + 2], "little")
    off += 2 + 4 * cslw
    if off + 2 > len(worddata):
        return (0, 0)
    cbRgFcLcb = int.from_bytes(worddata[off:off + 2], "little")
    off += 2
    idx = 33
    if idx * 8 + 8 > cbRgFcLcb * 8 or off + idx * 8 + 8 > len(worddata):
        return (0, 0)
    fcClx = int.from_bytes(worddata[off + idx*8:off + idx*8 + 4], "little")
    lcbClx = int.from_bytes(worddata[off + idx*8 + 4:off + idx*8 + 8], "little")
    return (fcClx, lcbClx)


def _parse_pieces(clx: bytes) -> list[tuple[int, int, int, bool]]:
    """Parse Pcdt/PlcPcd from a Clx blob.

    piece = (start_cp, end_cp, fc_byte_start, compressed).
    compressed=True → 8-bit (cp1251); False → UTF-16LE.
    Empty list if not parseable.
    """
    i = 0
    while i < len(clx):
        if clx[i] == 0x01:
            break
        if clx[i] == 0x02:
            if i + 5 > len(clx):
                return []
            lcbPrt = int.from_bytes(clx[i+1:i+5], "little")
            i += 5 + lcbPrt
        else:
            return []
    if i >= len(clx) or clx[i] != 0x01:
        return []
    i += 1
    if i + 4 > len(clx):
        return []
    lcbPlc = int.from_bytes(clx[i:i+4], "little")
    i += 4
    plc = clx[i:i + lcbPlc]
    if len(plc) < 8 or (len(plc) - 4) % 12 != 0:
        return []
    n = (len(plc) - 4) // 12
    cps = [int.from_bytes(plc[4 + j*4:8 + j*4], "little") for j in range(n + 1)]
    pcd_off = 4 + (n + 1) * 4
    pieces: list[tuple[int, int, int, bool]] = []
    for j in range(n):
        fc_raw = int.from_bytes(
            plc[pcd_off + j*8 + 2:pcd_off + j*8 + 6], "little"
        )
        compressed = bool(fc_raw & (1 << 30))
        fc = (fc_raw & 0x3FFFFFFF) >> (1 if compressed else 0)
        pieces.append((cps[j], cps[j+1], fc, compressed))
    return pieces


def _is_cyrillic(code: int) -> bool:
    return (
        0x0400 <= code <= 0x052F      # Cyrillic + Supplement
        or 0x2DE0 <= code <= 0x2DFF   # Cyrillic Extended C
        or 0xA640 <= code <= 0xA69F   # Cyrillic Extended B
        or 0x0530 <= code <= 0x058F
    )


def _text_score(text: str) -> int:
    """Выбор корректного decode для .doc по strongest signal.

    Ключ: длина **самой длинной** clean Cyrillic run'ы (>=12 символов,
    >=60% кириллицы). Реальный текст всегда содержит один длинный
    continuous run, тогда как неправильный decode бинарных участков
    WordDocument даёт только короткие run'ы. Сигнал «total runs length»
    недостоверен — cp1251 decode бинарного хвоста может дать много
    коротких чистых run'ов на «шуме».
    """
    longest = 0
    for m in _RUN_RE.finditer(text):
        run = m.group(0)
        if len(run) < 12:
            continue
        cyr = sum(1 for c in run if _is_cyrillic(ord(c)))
        if cyr >= len(run) * 0.6 and len(run) > longest:
            longest = len(run)
    return longest


def _pieces_to_text(worddata: bytes, pieces) -> str:
    parts: list[str] = []
    for start, end, fc, compressed in pieces:
        nchars = end - start
        nbytes = nchars if compressed else nchars * 2
        raw = worddata[fc : fc + nbytes]
        if not raw:
            continue
        s = raw.decode(
            "cp1251" if compressed else "utf-16-le", errors="replace"
        )
        buf: list[str] = []
        for ch in s:
            code = ord(ch)
            if code in (0x0D, 0x0A, 0x09, 0x07, 0x0B) or code < 32:
                buf.append(" ")
            else:
                buf.append(ch)
        parts.append("".join(buf))
    return "\n".join(parts)


def _doc_text_from_ole(path: str | Path) -> str:
    """Текст .doc (OLE2 Word 97-2003) через корректный parse FIB/PlcPcd;
    fallback — decode whole WordDocument stream."""
    path = Path(path)
    try:
        worddata = _read_ole_stream(path, "WordDocument")
    except Exception as exc:  # noqa: BLE001
        raise ExtractError(f"cannot read OLE stream {path}: {exc}") from exc

    if not worddata:
        raise ExtractError(f"{path}: no WordDocument stream")

    table_name = _fib_table_name(worddata)
    table = _read_ole_stream(path, table_name)

    candidates: list[str] = []
    fcClx, lcbClx = _fib_fcclx_lcbclx(worddata)
    if fcClx > 0 and lcbClx > 0 and fcClx + lcbClx <= len(table):
        pieces = _parse_pieces(table[fcClx : fcClx + lcbClx])
        if pieces:
            candidates.append(_pieces_to_text(worddata, pieces))
    for enc in ("utf-16-le", "cp1251"):
        candidates.append(worddata.decode(enc, errors="replace"))

    best = max(candidates, key=_text_score)
    text = "\n".join(" ".join(r.split()) for r in _RUN_RE.findall(best)).strip()
    if len(text) < 20:
        raise ExtractError(f"{path}: no extractable text in .doc")
    return text


def extract_doc(path: str | Path) -> list[StandaloneDocument]:
    path = Path(path)
    if not _has_ole_header(path):
        raise ExtractError(f"{path}: not an OLE2 .doc (wrong header)")
    text = _doc_text_from_ole(path)
    return [
        StandaloneDocument(
            source_file=str(path),
            kind="doc",
            title=_title_from_text(text, path.stem),
            page=None,
            text=text,
        )
    ]


def _has_ole_header(path: str | Path) -> bool:
    try:
        with open(path, "rb") as fp:
            head = fp.read(8)
    except OSError:
        return False
    return head[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


# ---------------------------------------------------------------------------
# XLSX (OOXML) — каждая sheet → отдельный StandaloneDocument
# ---------------------------------------------------------------------------
def extract_xlsx(path: str | Path) -> list[StandaloneDocument]:
    import openpyxl

    path = Path(path)
    try:
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise ExtractError(f"cannot open xlsx {path}: {exc}") from exc

    docs: list[StandaloneDocument] = []
    for ws in wb.worksheets:
        lines: list[str] = []
        for row in ws.iter_rows(values_only=True):
            cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if cells:
                lines.append(" | ".join(cells))
        if not lines:
            continue
        text = "\n".join(lines)
        docs.append(
            StandaloneDocument(
                source_file=str(path),
                kind="xlsx",
                title=_title_from_text(text, ws.title),
                page=None,
                sheet=ws.title,
                text=text,
            )
        )
    wb.close()
    if not docs:
        raise ExtractError(f"{path}: no non-empty sheets")
    return docs


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
_EXTRACTORS: dict[str, object] = {
    ".txt": extract_txt,
    ".pdf": extract_pdf,
    ".docx": extract_docx,
    ".doc": extract_doc,
    ".xlsx": extract_xlsx,
}


def extract_file(path: str | Path) -> list[StandaloneDocument]:
    """Извлекает StandaloneDocument(ы) из файла по расширению.

    Бросает :class:`ExtractError` (и OSError), если файл не читается/пустой.
    """
    ext = Path(path).suffix.lower()
    extractor = _EXTRACTORS.get(ext)
    if extractor is None:
        raise ExtractError(f"unsupported format: {ext or '(no extension)'}")
    return extractor(str(path))  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Скан каталога
# ---------------------------------------------------------------------------
def scan_standalone_files(
    root: str | Path,
    include_exts: Iterable[str] = STANDALONE_EXTENSIONS,
    *,
    exclude_junk: bool = True,
) -> tuple[list[Path], list[tuple[Path, str]]]:
    """Рекурсивно собирает подходящие файлы и список пропущенных.

    Returns:
        ``(files, skipped)``; ``skipped`` — пары ``(path, reason)``.
    """
    root = Path(root)
    include = {e.lower() for e in include_exts}
    files: list[Path] = []
    skipped: list[tuple[Path, str]] = []

    if not root.exists():
        raise FileNotFoundError(f"scan root not found: {root}")

    for dp, dirs, fnames in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in fnames:
            full = Path(dp) / name
            if exclude_junk and _is_junk(name):
                skipped.append((full, "junk/temp file"))
                continue
            if full.suffix.lower() not in include:
                skipped.append((full, f"unsupported ext '{full.suffix}'"))
                continue
            files.append(full)

    files.sort()
    return files, skipped


def ingest_standalone_dir(
    root: str | Path,
    include_exts: Iterable[str] = STANDALONE_EXTENSIONS,
    *,
    on_error: str = "skip",
) -> dict:
    """Извлекает все standalone-документы из дерева ``root``.

    ``on_error``:
      - ``"skip"``  — неудачные файлы попадают в ``errors``;
      - ``"raise"`` — первое исключение пробрасывается.

    Возвращает статистику с извлечёнными ``documents``.
    """
    files, skipped_by_scan = scan_standalone_files(root, include_exts)

    documents: list[StandaloneDocument] = []
    extracted_paths: list[Path] = []
    errors: list[tuple[Path, str]] = []

    for path in files:
        try:
            docs = extract_file(path)
        except Exception as exc:  # noqa: BLE001
            if on_error == "raise":
                raise
            errors.append((path, str(exc)))
            continue
        except OSError as exc:
            if on_error == "raise":
                raise
            errors.append((path, str(exc)))
            continue
        else:
            documents.extend(docs)
            extracted_paths.append(path)

    for path, reason in skipped_by_scan:
        errors.append((path, f"skipped: {reason}"))

    return {
        "files_discovered": len(files) + len(skipped_by_scan),
        "files_extracted": len(extracted_paths),
        "files_skipped": len(skipped_by_scan),
        "files_error": sum(1 for _ in errors if not _[1].startswith("skipped")),
        "skipped": [
            {"path": str(p), "reason": r} for p, r in skipped_by_scan
        ],
        "errors": [
            {"path": str(p), "reason": r} for p, r in errors
            if not r.startswith("skipped")
        ],
        "documents": documents,
        "by_extension": _count_extensions(files, skipped_by_scan),
    }


def _count_extensions(
    files: list[Path],
    skipped: list[tuple[Path, str]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for p in files:
        e = p.suffix.lower() or "(none)"
        counts[e] = counts.get(e, 0) + 1
    for p, _ in skipped:
        e = p.suffix.lower() or "(none)"
        counts.setdefault(e, 0)
    return counts

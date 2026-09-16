"""
parsers.py — normalizes PDF / DOCX / XLSX into plain-text sections.

Per spec Section 7.2: `unstructured` is the primary parser for PDF/DOCX
(layout-aware section detection). It has a heavier dependency chain
(poppler/libreoffice in some install modes) that may not install cleanly
on a shared host without root. The pure-Python fallback (pypdf +
python-docx) is an accepted substitute at the cost of losing
layout-aware section detection (Section 13.1 assumption).

This module is a private implementation detail behind ingest_source()
(Section 7.5) — nothing outside the ingestion package should import
these functions directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A numbered section heading, e.g. "1. Scope", "2.1 Escalation", "3) Review".
_NUMBERED_HEADING_RE = re.compile(r"^\s*\d+(?:\.\d+)*[.)]?\s+\S")
# Upper bound on a plausible heading; longer strings are treated as body text.
_MAX_HEADING_LEN = 120


def _looks_like_heading(el_type: str, text: str) -> bool:
    """
    Decide whether an `unstructured` element is a SECTION HEADING.

    `unstructured` over-labels body text as `Title` on some PDFs (wrapped
    sentence fragments, e.g. "channel for Severity 1."), while the REAL
    numbered headings often arrive as `ListItem` ("1. Scope"). So classify by
    shape, not element type (issue #1):

      - a numbered-heading pattern ("1.", "2.1", "3)") is a heading whatever
        its element type;
      - a `Title`/`Header` is a heading ONLY if it looks like one: short,
        does not end with a sentence period, and starts with an uppercase
        letter or digit.
    """
    if _NUMBERED_HEADING_RE.match(text):
        return True
    if el_type in ("Title", "Header"):
        if len(text) > _MAX_HEADING_LEN:
            return False
        if text.endswith("."):
            return False
        return text[:1].isupper() or text[:1].isdigit()
    return False


@dataclass
class ParsedSection:
    section_title: str | None
    text: str
    page: int | None = None  # source page number; PDFs only (SPEC §22.4)


def count_embedded_images(file_path: str, source_type: str) -> int:
    """
    SPEC §15.1 — count the embedded raster images in a PDF/DOCX, so the Owner
    can be told "N images — their content is not indexed". Returns 0 for
    XLSX (no meaningful embedded-image count for this purpose).

    Uses only what is already installed; never raises — a count failure is a
    floor, not an error.

    KNOWN LIMITATION (documented in SPEC §15.1 / memory.md): the count is a
    FLOOR. Vector diagrams and curve-rendered text may not register as
    countable raster images, so this is a lower bound on embedded images, not
    an exact figure, and it never reflects semantic content.
    """
    try:
        if source_type == "pdf":
            return _count_images_pdf(file_path)
        if source_type == "docx":
            return _count_images_docx(file_path)
        return 0  # xlsx
    except Exception:  # noqa: BLE001 - count is informational; never block ingest
        return 0


def _count_images_pdf(file_path: str) -> int:
    """Try `unstructured`'s element stream first (Image/Figure elements),
    fall back to a pypdf XObject scan of each page."""
    try:
        from unstructured.partition.pdf import partition_pdf

        elements = partition_pdf(filename=file_path)
        return sum(1 for el in elements if type(el).__name__ in ("Image", "Figure"))
    except Exception:  # noqa: BLE001
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        total = 0
        for page in reader.pages:
            try:
                xobjects = page.get("/Resources", {}).get("/XObject", {}) or {}
            except Exception:  # noqa: BLE001
                continue
            total += sum(
                1 for xobj in xobjects.values()
                if xobj.get_object().get("/Subtype") == "/Image"
            )
        return total


def _count_images_docx(file_path: str) -> int:
    """python-docx inline_shapes + drawings; fall back to the `unstructured`
    DOCX element stream (Image elements)."""
    try:
        import docx  # python-docx

        document = docx.Document(file_path)
        return len(document.inline_shapes)
    except Exception:  # noqa: BLE001
        try:
            from unstructured.partition.docx import partition_docx

            elements = partition_docx(filename=file_path)
            return sum(1 for el in elements if type(el).__name__ == "Image")
        except Exception:  # noqa: BLE001
            return 0


def _normalise_furniture_line(line: str) -> str:
    """
    Normalise a line for furniture comparison (SPEC §22.5): collapse whitespace
    and replace digit runs with '#', so lines differing only by a page number
    compare equal.
    """
    return re.sub(r"\d+", "#", " ".join(line.split()))


def _remove_page_furniture(pages_lines: dict[int, list[str]]) -> dict[int, list[str]]:
    """
    SPEC §22.5 — page furniture, by repetition only.

    A line is removed **only if it appears on EVERY page** of a document of
    **two or more pages**, after digit normalisation. Repetition across pages is
    the evidence; there is **no** word pattern-matching. **Never applied to a
    single-page document.** If removal would empty a page entirely, the
    furniture is **RETAINED for that page** so no page's text is discarded.
    """
    if len(pages_lines) < 2:
        return pages_lines
    all_pages = set(pages_lines)
    line_pages: dict[str, set[int]] = {}
    for page, lines in pages_lines.items():
        for line in lines:
            key = _normalise_furniture_line(line)
            if key:
                line_pages.setdefault(key, set()).add(page)
    furniture = {key for key, pages in line_pages.items() if pages >= all_pages}
    if not furniture:
        return pages_lines
    result: dict[int, list[str]] = {}
    for page, lines in pages_lines.items():
        kept = [ln for ln in lines if _normalise_furniture_line(ln) not in furniture]
        if not any(ln.strip() for ln in kept):
            kept = list(lines)  # would empty the page → retain its furniture
        result[page] = kept
    return result


def _pdf_sections_by_page(elements) -> list[ParsedSection]:
    """
    Group PDF elements by their page number and emit one page-labelled section
    per page, after furniture removal (SPEC §22.4, §22.5). No section title is
    inferred for a PDF.
    """
    pages_lines: dict[int, list[str]] = {}
    for el in elements:
        text = str(el).strip()
        if not text:
            continue
        page = getattr(getattr(el, "metadata", None), "page_number", None) or 1
        pages_lines.setdefault(page, []).append(text)
    pages_lines = _remove_page_furniture(pages_lines)
    sections: list[ParsedSection] = []
    for page in sorted(pages_lines):
        body = "\n\n".join(pages_lines[page])
        if body.strip():
            sections.append(ParsedSection(section_title=None, page=page, text=body))
    return sections


def parse_pdf(file_path: str) -> list[ParsedSection]:
    """
    SPEC §22.4 (Item 3): PDFs are labelled by PAGE NUMBER, not by inferred
    section titles. The element list is flat and a multi-column layout
    interleaves it, so an inferred heading can be paired with the wrong body; a
    page number is a checkable fact, an inferred section title is a claim that
    can be wrong. Elements are grouped by page number and repeated page
    furniture is removed (§22.5). Falls back to pypdf (text layer only, one
    section per page) if unstructured is unavailable or errors.
    """
    try:
        from unstructured.partition.pdf import partition_pdf

        elements = partition_pdf(filename=file_path)
    except Exception:
        return _parse_pdf_fallback(file_path)
    return _pdf_sections_by_page(elements)


def _parse_pdf_fallback(file_path: str) -> list[ParsedSection]:
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    pages_lines: dict[int, list[str]] = {}
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages_lines[i] = [ln for ln in text.splitlines() if ln.strip()]
    pages_lines = _remove_page_furniture(pages_lines)
    sections: list[ParsedSection] = []
    for page in sorted(pages_lines):
        body = "\n\n".join(pages_lines[page])
        if body.strip():
            sections.append(ParsedSection(section_title=None, page=page, text=body))
    return sections


def parse_docx(file_path: str) -> list[ParsedSection]:
    """
    Try `unstructured`'s partition_docx first (splits by heading).
    Falls back to python-docx (paragraph concatenation, no heading
    detection) if unavailable.
    """
    try:
        from unstructured.partition.docx import partition_docx

        elements = partition_docx(filename=file_path)
        return _group_unstructured_elements(elements)
    except Exception:
        return _parse_docx_fallback(file_path)


def _parse_docx_fallback(file_path: str) -> list[ParsedSection]:
    import docx  # python-docx

    document = docx.Document(file_path)
    current_title = None
    current_paras: list[str] = []
    sections: list[ParsedSection] = []

    def flush():
        if current_paras:
            sections.append(
                ParsedSection(section_title=current_title, text="\n\n".join(current_paras))
            )

    for para in document.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = (para.style.name or "") if para.style else ""
        if style.lower().startswith("heading"):
            flush()
            current_title = text
            current_paras = []
        else:
            current_paras.append(text)
    flush()

    if not sections:
        # No headings detected at all — treat whole doc as one section.
        all_text = "\n\n".join(p.text.strip() for p in document.paragraphs if p.text.strip())
        if all_text:
            sections.append(ParsedSection(section_title=None, text=all_text))

    return sections


def _is_empty_cell(value) -> bool:
    """A cell counts as empty when it is missing/NaN or blank after stripping."""
    try:
        import pandas as pd

        if pd.isna(value):
            return True
    except Exception:  # noqa: BLE001 - not a pandas scalar; fall through to text
        pass
    return str(value).strip() == ""


def _cell_is_text(value) -> bool:
    """
    SPEC §22.2 TEXT GUARD. An empty cell is ignored; a non-empty cell is TEXT
    only if it is a string — a number or a date is not text.
    """
    if _is_empty_cell(value):
        return True
    return isinstance(value, str)


def _detect_xlsx_header(raw_rows: list[list], max_scan: int = 10):
    """
    SPEC §22.2 — the header rule (amended 2026-09-16).

    MAX is the greatest number of non-empty cells in any row of the sheet. A
    CANDIDATE is a row among the FIRST 10 rows whose non-empty-cell count equals
    MAX. The provisional header is the FIRST (topmost) candidate. TEXT GUARD:
    detection is CONFIDENT only if every non-empty cell in that provisional
    header row is TEXT (no number, no date); if that row contains any number or
    date, detection is AMBIGUOUS. ONLY the topmost candidate is tested — there is
    NO fall-through to the next candidate. Zero candidates is AMBIGUOUS. A sheet
    with no non-empty cell at all has NO identifiable header.

    Returns (state, header_index), state in {"confident", "ambiguous", "none"};
    header_index is None unless confident.
    """
    widths = [sum(1 for cell in row if not _is_empty_cell(cell)) for row in raw_rows]
    max_width = max(widths) if widths else 0
    if max_width == 0:
        return "none", None
    candidates = [i for i, width in enumerate(widths[:max_scan]) if width == max_width]
    if not candidates:
        return "ambiguous", None
    header_index = candidates[0]
    if not all(_cell_is_text(cell) for cell in raw_rows[header_index]):
        return "ambiguous", None
    return "confident", header_index


def _trimmed_width(rows: list[list]) -> int:
    """Number of columns up to the last non-empty cell across the given rows."""
    width = 0
    for row in rows:
        for j, cell in enumerate(row):
            if not _is_empty_cell(cell):
                width = max(width, j + 1)
    return width


def _cell_text(value) -> str:
    return "" if _is_empty_cell(value) else str(value).strip()


def parse_xlsx(file_path: str) -> list[ParsedSection]:
    """
    Per SPEC §7.2: one text block per sheet — a markdown-style table rendering
    plus a short auto-generated summary line. No query engine, no multi-sheet
    joins (explicitly out of scope, Section 4.1).

    Per SPEC §22.2 (Item 1): the real header row is DETECTED, not assumed, using
    the amended header rule in `_detect_xlsx_header`. The data-row count is the
    count of rows AFTER the header, and the rendered table carries an explicit
    1-based row-number column so the count is visible and checkable. AMBIGUOUS
    (zero candidates, or a number/date in the topmost candidate) falls back to
    first-row-as-header and STATES that in the rendered sheet text.
    """
    import pandas as pd

    raw_sheets = pd.read_excel(file_path, sheet_name=None, header=None, engine="openpyxl")
    sections: list[ParsedSection] = []

    for sheet_name, raw in raw_sheets.items():
        rows = raw.values.tolist() if raw is not None else []
        state, header_index = _detect_xlsx_header(rows)
        if header_index is None:
            header_index = 0
        header_row = rows[header_index] if rows else []
        data_rows = rows[header_index + 1:] if rows else []

        n_cols = _trimmed_width([header_row] + data_rows)
        columns = ["#"]
        for j in range(n_cols):
            name = _cell_text(header_row[j]) if j < len(header_row) else ""
            columns.append(name if name else f"Column {j + 1}")
        table_rows = []
        for i, row in enumerate(data_rows, start=1):
            table_rows.append(
                [i] + [_cell_text(row[j]) if j < len(row) else "" for j in range(n_cols)]
            )
        table_md = pd.DataFrame(table_rows, columns=columns).to_markdown(index=False)

        if state == "confident":
            summary = (
                f"Sheet '{sheet_name}' — confident header at row {header_index + 1} "
                f"(1-based): {len(data_rows)} data rows, {n_cols} columns."
            )
        elif state == "ambiguous":
            summary = (
                f"Sheet '{sheet_name}' — header row not determined confidently "
                f"(ambiguous shape): assuming the first row is the header. "
                f"{len(data_rows)} data rows, {n_cols} columns."
            )
        else:
            summary = (
                f"Sheet '{sheet_name}' — no header row could be identified: "
                f"assuming the first row is the header. "
                f"{len(data_rows)} data rows, {n_cols} columns."
            )

        text = f"{summary}\n\n{table_md}"
        sections.append(ParsedSection(section_title=sheet_name, text=text))

    return sections


def _group_unstructured_elements(elements) -> list[ParsedSection]:
    """
    Groups a flat list of `unstructured` elements into sections keyed by the
    most recent heading. Heading detection is by SHAPE (`_looks_like_heading`),
    not by element type alone — see issue #1: PDF `partition_pdf` labels body
    sentence fragments as `Title` while the real numbered headings arrive as
    `ListItem`. Elements before the first heading are grouped under
    section_title=None.

    SPEC §22.3 (Item 2) — NO TEXT IS DISCARDED AT GROUPING. A heading immediately
    followed by another heading (or a trailing heading at end of document) has no
    body of its own, so its text is CARRIED into the body of the next section
    that is emitted; a trailing heading becomes a body-only section. Previously
    the `if current_texts:` guard dropped such headings together with their text.
    """
    sections: list[ParsedSection] = []
    current_title: str | None = None
    current_texts: list[str] = []
    carried: list[str] = []

    def flush():
        nonlocal current_title, current_texts, carried
        if current_texts:
            body = carried + current_texts
            sections.append(
                ParsedSection(section_title=current_title, text="\n\n".join(body))
            )
            carried = []
        elif current_title is not None:
            # A heading with no body: keep its text, never discard it.
            carried.append(current_title)
        current_title = None
        current_texts = []

    for el in elements:
        el_type = type(el).__name__
        el_text = str(el).strip()
        if not el_text:
            continue
        if _looks_like_heading(el_type, el_text):
            flush()
            current_title = el_text
        else:
            current_texts.append(el_text)

    flush()
    # A trailing heading (end of document) has no following section to carry
    # into, so it is preserved as a body-only section.
    if carried:
        sections.append(ParsedSection(section_title=None, text="\n\n".join(carried)))

    return sections


def parse(file_path: str, source_type: str) -> list[ParsedSection]:
    """Dispatch by source_type. Raises ValueError for unsupported types."""
    if source_type == "pdf":
        return parse_pdf(file_path)
    if source_type == "docx":
        return parse_docx(file_path)
    if source_type == "xlsx":
        return parse_xlsx(file_path)
    raise ValueError(f"Unsupported source_type for parsing: {source_type!r}")

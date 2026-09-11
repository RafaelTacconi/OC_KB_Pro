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

from dataclasses import dataclass


@dataclass
class ParsedSection:
    section_title: str | None
    text: str


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


def parse_pdf(file_path: str) -> list[ParsedSection]:
    """
    Try `unstructured`'s partition_pdf first (layout-aware: detects
    headings/sections). Falls back to pypdf (text-layer only, one
    section per page) if unstructured is unavailable or errors.
    """
    try:
        from unstructured.partition.pdf import partition_pdf

        elements = partition_pdf(filename=file_path)
        return _group_unstructured_elements(elements)
    except Exception:
        return _parse_pdf_fallback(file_path)


def _parse_pdf_fallback(file_path: str) -> list[ParsedSection]:
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    sections = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            sections.append(ParsedSection(section_title=f"Page {i}", text=text.strip()))
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


def parse_xlsx(file_path: str) -> list[ParsedSection]:
    """
    Per spec Section 7.2: one text block per sheet — a markdown-style table
    rendering plus a short auto-generated summary line. No query engine,
    no multi-sheet joins (explicitly out of scope, Section 4.1).
    """
    import pandas as pd

    sections: list[ParsedSection] = []
    sheets = pd.read_excel(file_path, sheet_name=None, engine="openpyxl")

    for sheet_name, df in sheets.items():
        if df.empty:
            continue
        n_rows, n_cols = df.shape
        columns = ", ".join(str(c) for c in df.columns)
        summary = f"Sheet '{sheet_name}' has {n_rows} rows and columns: {columns}."
        table_md = df.to_markdown(index=False)
        text = f"{summary}\n\n{table_md}"
        sections.append(ParsedSection(section_title=sheet_name, text=text))

    return sections


def _group_unstructured_elements(elements) -> list[ParsedSection]:
    """
    Groups a flat list of `unstructured` elements into sections keyed by
    the most recent Title/Header element seen. Elements before the first
    title are grouped under section_title=None.
    """
    sections: list[ParsedSection] = []
    current_title: str | None = None
    current_texts: list[str] = []

    def flush():
        if current_texts:
            sections.append(
                ParsedSection(section_title=current_title, text="\n\n".join(current_texts))
            )

    for el in elements:
        el_type = type(el).__name__
        el_text = str(el).strip()
        if not el_text:
            continue
        if el_type in ("Title", "Header"):
            flush()
            current_title = el_text
            current_texts = []
        else:
            current_texts.append(el_text)
    flush()

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

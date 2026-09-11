"""
test_image_count.py — SPEC.md §15.1 / acceptance criteria A26, A27.

A26 — for each ingested PDF/DOCX, the `sources` row stores an `image_count`;
      it is 0 or more and never blocks ingestion.
A27 — Manage → Knowledge shows the Owner a per-file note
      "N images — their content is not indexed" when image_count > 0.

Tests the count function directly (no new dependency: pypdf + python-docx are
already installed) and the schema/migration, then the UI note via AppTest.
"""

from __future__ import annotations

import io
import sqlite3
import uuid
from pathlib import Path

import pytest

from ingestion import parsers

_NOW = "2026-09-11T00:00:00+00:00"


def _make_pdf_with_image(out: Path, n_images: int) -> None:
    """Build a minimal PDF with n inline image XObjects using pypdf (installed)."""
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, NumberObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    # a tiny 1x1 image
    png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + bytes(
        [0, 0, 0, 1, 0, 0, 0, 1, 8, 6, 0, 0, 0]  # 1x1 RGBA
    ) + b"\x00\x00\x00\x00IDAT\x08\xd7c\xf8\x0f\x00\x00\x01\x01\x00\x00" + b"\x00\x00\x00\x00IEND"
    resources = DictionaryObject()
    xobjects = DictionaryObject()
    for i in range(n_images):
        img = writer._add_object(
            DictionaryObject({
                NameObject("/Type"): NameObject("/XObject"),
                NameObject("/Subtype"): NameObject("/Image"),
                NameObject("/Width"): NumberObject(1),
                NameObject("/Height"): NumberObject(1),
                NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
                NameObject("/BitsPerComponent"): NumberObject(8),
                NameObject("/Length"): NumberObject(len(png)),
            })
        )
        # attach raw bytes via the stream
        img._data = png  # type: ignore[attr-defined]
        xobjects[NameObject(f"/Im{i}")] = img
    resources[NameObject("/XObject")] = xobjects
    page[NameObject("/Resources")] = resources
    with open(out, "wb") as f:
        writer.write(f)


def _make_docx_with_image(out: Path, n_images: int) -> None:
    """Build a DOCX with n inline images via python-docx (installed)."""
    import docx
    from docx.shared import Inches

    d = docx.Document()
    d.add_paragraph("some text")
    # A real 1x1 PNG via Pillow (installed as an unstructured dependency).
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (1, 1), (255, 0, 0)).save(buf, format="PNG")
    buf.seek(0)
    for _ in range(n_images):
        buf.seek(0)
        d.add_picture(buf, width=Inches(1))
    d.save(str(out))


def test_count_pdf_images():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "a.pdf"
        _make_pdf_with_image(p, 3)
        # pypdf XObject fallback counts the 3 image XObjects
        assert parsers.count_embedded_images(str(p), "pdf") == 3


def test_count_docx_images():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "a.docx"
        _make_docx_with_image(p, 2)
        # python-docx inline_shapes count = 2
        assert parsers.count_embedded_images(str(p), "docx") == 2


def test_count_is_floor_and_never_raises(monkeypatch):
    # A non-existent path / bad file must not raise — returns 0 (a floor).
    assert parsers.count_embedded_images("nope.pdf", "pdf") == 0
    assert parsers.count_embedded_images("nope.docx", "docx") == 0
    # xlsx has no count
    assert parsers.count_embedded_images("x.xlsx", "xlsx") == 0


def test_migrate_db_adds_image_count_column(tmp_path):
    """The migration adds sources.image_count to a legacy DB (A26 schema)."""
    import db as db_module

    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.chdir(tmp_path)
    db_module.init_db()
    conn = db_module.get_connection()
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(sources)")]
        assert "image_count" in cols
    finally:
        conn.close()
    monkeypatch.undo()


def test_owner_sees_image_note_in_manage(monkeypatch, tmp_path):
    """A27 — Manage → Knowledge shows the image note for a source with images."""
    from streamlit.testing.v1 import AppTest

    REPO_ROOT = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(tmp_path)
    import db as db_module

    db_module.init_db()
    db_module.migrate_db()
    # seed users/workspace so FKs hold
    from config import bootstrap

    bootstrap()

    source_id = uuid.uuid4().hex
    conn = db_module.get_connection()
    try:
        conn.execute(
            "INSERT INTO sources (source_id, workspace_id, source_type, display_name, "
            "origin_ref, status, error_message, indexed_at, image_count, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (source_id, "aml-workspace", "pdf", "images.pdf",
             "data/aml-workspace/sources/x.pdf", "indexed", None, _NOW, 4, _NOW),
        )
        conn.commit()
    finally:
        conn.close()

    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    at.button(key="nav_manage").click().run()
    assert not at.exception, list(at.exception)
    # The note is rendered as a caption: "4 images — their content is not indexed"
    assert any("4 images" in c.value and "not indexed" in c.value for c in at.caption)
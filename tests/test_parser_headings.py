"""
test_parser_headings.py — issue #1: section-title extraction.

Reproduced against the real PDFs: `unstructured.partition_pdf` labels wrapped
body sentence FRAGMENTS as `Title` ("Financial Crime Oversight Committee.",
"channel for Severity 1.", "than 15 minutes.") while the REAL numbered headings
arrive as `ListItem` ("1. Scope", "2. Escalation Timeline"). The old
_group_unstructured_elements keyed on element type alone, so it used exactly the
wrong elements.

Fix: classify by shape — numbered pattern is a heading, and a Title/Header is a
heading only if it looks like one (short, no trailing period, uppercase/digit
start).

These tests use tiny fake elements whose CLASS NAMES match the unstructured
element types the grouping code dispatches on.
"""

from __future__ import annotations

from ingestion.parsers import _group_unstructured_elements, _looks_like_heading


class Title:
    def __init__(self, text): self._t = text
    def __str__(self): return self._t


class Header:
    def __init__(self, text): self._t = text
    def __str__(self): return self._t


class ListItem:
    def __init__(self, text): self._t = text
    def __str__(self): return self._t


class NarrativeText:
    def __init__(self, text): self._t = text
    def __str__(self): return self._t


class Text:
    def __init__(self, text): self._t = text
    def __str__(self): return self._t


def test_looks_like_heading_numbered_is_heading():
    # Numbered headings are commonly ListItem in PDFs — must be headings.
    assert _looks_like_heading("ListItem", "1. Scope")
    assert _looks_like_heading("ListItem", "2.1 Escalation Timeline")
    assert _looks_like_heading("ListItem", "3) Review")


def test_looks_like_heading_rejects_sentence_fragments():
    # The spurious Titles observed in the real PDFs — all end with a period.
    assert not _looks_like_heading("Title", "Financial Crime Oversight Committee.")
    assert not _looks_like_heading("Title", "channel for Severity 1.")
    assert not _looks_like_heading("Title", "than 15 minutes.")
    assert not _looks_like_heading("Title", "further senior manager.")
    # lower-case start = wrapped continuation
    assert not _looks_like_heading("Title", "from the end of the customer relationship.")


def test_looks_like_heading_accepts_real_titles():
    assert _looks_like_heading(
        "Title",
        "Security Incident Management Policy Document SEC-POL-07 — Information Security — Version 3",
    )
    assert _looks_like_heading("Title", "Section 3 - Financial Crime Oversight Committee")


def test_grouping_uses_real_numbered_headings_not_spurious_titles():
    elements = [
        Title("Anti-Money Laundering Policy Document AML-POL-04 — Financial Crime Team"),
        ListItem("1. Scope"),
        NarrativeText("This policy covers the firm's AML obligations."),
        ListItem("2. Escalation Timeline"),
        NarrativeText("A suspicious activity report must be raised within 12 hours."),
        # spurious Title that the old code would have taken as a section title
        Title("Financial Crime Oversight Committee."),
        NarrativeText("Approved deviations are reviewed quarterly."),
        ListItem("3. Approval Authority for Deviations"),
        NarrativeText("Only the Head of Financial Crime may approve a deviation."),
    ]
    sections = _group_unstructured_elements(elements)
    titles = [s.section_title for s in sections]

    # Real numbered headings are the section titles.
    assert "1. Scope" in titles
    assert "2. Escalation Timeline" in titles
    assert "3. Approval Authority for Deviations" in titles
    # The sentence fragment is NOT a section title anywhere.
    assert "Financial Crime Oversight Committee." not in titles
    # ...it is body text under the preceding section instead.
    esc = next(s for s in sections if s.section_title == "2. Escalation Timeline")
    assert "Financial Crime Oversight Committee." in esc.text


def test_docx_style_real_titles_still_work():
    elements = [
        Header("Section 2 - Financial Crime Oversight Committee"),
        NarrativeText("Body one."),
        Header("Section 3 - Account Restrictions"),
        NarrativeText("Body two."),
    ]
    sections = _group_unstructured_elements(elements)
    assert [s.section_title for s in sections] == [
        "Section 2 - Financial Crime Oversight Committee",
        "Section 3 - Account Restrictions",
    ]
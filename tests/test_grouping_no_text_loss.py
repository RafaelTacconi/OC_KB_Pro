"""
test_grouping_no_text_loss.py — SPEC §22.3 (Item 2); criterion A67.

`_group_unstructured_elements` is unit-tested directly on synthetic element
lists; no file is needed. These tests exercise the shapes the old
`if current_texts:` guard dropped — headings with no body of their own — which
the nine synthetic corpus documents do not contain.

Fake elements mirror the class-name dispatch used by the grouping code (as in
tests/test_parser_headings.py).
"""

from __future__ import annotations

from ingestion.parsers import _group_unstructured_elements


class Title:
    def __init__(self, text): self._t = text
    def __str__(self): return self._t


class NarrativeText:
    def __init__(self, text): self._t = text
    def __str__(self): return self._t


def _combined_text(sections) -> str:
    parts = []
    for s in sections:
        parts.append(s.section_title or "")
        parts.append(s.text)
    return "\n".join(parts)


def test_heading_followed_by_heading_is_not_discarded():
    # The first heading has no body before the next heading — old code dropped it.
    sections = _group_unstructured_elements([
        Title("Alpha"),
        Title("Beta"),
        NarrativeText("body"),
    ])
    combined = _combined_text(sections)
    assert "Alpha" in combined  # carried, not discarded
    assert "Beta" in combined
    assert "body" in combined


def test_three_headings_in_a_row_then_body_loses_nothing():
    sections = _group_unstructured_elements([
        Title("H1"),
        Title("H2"),
        Title("H3"),
        NarrativeText("only body"),
    ])
    combined = _combined_text(sections)
    for text in ("H1", "H2", "H3", "only body"):
        assert text in combined


def test_trailing_heading_at_end_of_document_is_preserved():
    sections = _group_unstructured_elements([
        Title("H1"),
        NarrativeText("its body"),
        Title("Trailing"),
    ])
    combined = _combined_text(sections)
    assert "Trailing" in combined


def test_normal_heading_body_grouping_is_unchanged():
    sections = _group_unstructured_elements([
        Title("H1"),
        NarrativeText("b1"),
        Title("H2"),
        NarrativeText("b2"),
    ])
    assert [s.section_title for s in sections] == ["H1", "H2"]
    assert [s.text for s in sections] == ["b1", "b2"]


def test_invariant_no_non_empty_element_text_is_lost():
    elements = [
        Title("Alpha"),
        Title("Beta"),
        NarrativeText("body one"),
        Title("Gamma"),
        Title("Delta"),
        NarrativeText("body two"),
        Title("Trailing"),
    ]
    sections = _group_unstructured_elements(elements)
    combined = _combined_text(sections)
    for el in elements:
        text = str(el).strip()
        assert text in combined, f"lost element text: {text!r}"

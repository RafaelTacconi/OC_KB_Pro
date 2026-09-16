"""
test_xlsx_header_detection.py — SPEC §22.2 (Item 1); criteria A64/A65/A66.

These tests build their OWN .xlsx files under pytest's tmp_path. The nine
synthetic corpus documents are clean single-header sheets and cannot exhibit this
defect, and no real corpus document or content is used here.

The rule tested is the AMENDED §22.2 rule (2026-09-16): MAX = greatest number of
non-empty cells in any row; a candidate is a row among the first 10 with MAX
non-empty cells; the provisional header is the FIRST (topmost) candidate; TEXT
GUARD — CONFIDENT only if every non-empty cell in that row is text (no number, no
date), tested on the topmost candidate ONLY (no fall-through); zero candidates is
AMBIGUOUS; AMBIGUOUS falls back to first-row-as-header with the uncertainty
stated in the rendered text.
"""

from __future__ import annotations

import datetime
import re

import pandas as pd

from ingestion.parsers import parse_xlsx


def _write_xlsx(path, sheets: dict):
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, rows in sheets.items():
            pd.DataFrame(rows).to_excel(writer, sheet_name=name, index=False, header=False)


def _only_section(path):
    sections = parse_xlsx(str(path))
    assert len(sections) == 1
    assert sections[0].text.strip()  # rendered sheet is non-empty
    return sections[0]


def test_title_block_above_header_finds_real_header_and_true_count(tmp_path):
    # Title row and subtitle row ABOVE the real header. Every data row is the SAME
    # width as the header — the shape that failed under the withdrawn rule. The
    # topmost candidate is the real header row (all text), so this must be
    # CONFIDENT, not the fallback.
    path = tmp_path / "title_block.xlsx"
    _write_xlsx(path, {"Report": [
        ["Quarterly Reconciliation Report", None, None],
        ["Prepared by Operations", None, None],
        ["Account", "Amount", "Date"],
        ["A1", 100, "2026-01-01"],
        ["A2", 200, "2026-01-02"],
        ["A3", 300, "2026-01-03"],
    ]})
    section = _only_section(path)
    assert "confident header at row 3" in section.text
    assert "3 data rows" in section.text
    assert "Account" in section.text
    assert "Amount" in section.text
    # Rows above the header are not counted as data.
    assert "Quarterly Reconciliation Report" not in section.text
    assert "Prepared by Operations" not in section.text
    # This is the confident path — NO uncertainty text.
    assert "not determined confidently" not in section.text
    assert "no header row could be identified" not in section.text


def test_header_in_first_row_is_confident_and_unchanged(tmp_path):
    path = tmp_path / "first_row.xlsx"
    _write_xlsx(path, {"S": [
        ["Name", "Value"],
        ["x", 1],
        ["y", 2],
    ]})
    section = _only_section(path)
    assert "confident header at row 1" in section.text
    assert "2 data rows" in section.text
    assert "not determined confidently" not in section.text


def test_text_guard_triggers_on_number_in_topmost_candidate(tmp_path):
    # The topmost candidate row contains numbers, so the TEXT GUARD fails.
    path = tmp_path / "guard_numbers.xlsx"
    _write_xlsx(path, {"S": [
        [2026, 100, 200],
        ["Name", "Value", "Note"],
        ["a", "b", "c"],
    ]})
    section = _only_section(path)
    assert "not determined confidently" in section.text
    assert "assuming the first row is the header" in section.text
    # Fallback uses the first row as the header.
    assert re.search(r"\|\s*#\s*\|\s*2026\s*\|\s*100", section.text)


def test_no_fall_through_to_a_later_text_candidate(tmp_path):
    # Topmost candidate carries a DATE (guard fails). A LATER candidate is all
    # text and would pass the guard — but the rule must NOT walk on to it.
    path = tmp_path / "no_fall_through.xlsx"
    _write_xlsx(path, {"S": [
        [datetime.date(2026, 1, 1), 100, 200],
        ["Name", "Value", "Note"],
        ["a", "b", "c"],
    ]})
    section = _only_section(path)
    assert "not determined confidently" in section.text
    # Header stays on the first row (the fallback), NOT the later text candidate.
    assert re.search(r"\|\s*#\s*\|\s*2026-01-01", section.text)


def test_zero_candidates_widest_row_outside_first_10_is_ambiguous(tmp_path):
    # The widest row is row 11 (0-based 10), outside the first-10 window, so there
    # are ZERO candidates -> AMBIGUOUS.
    path = tmp_path / "zero_candidates.xlsx"
    rows = [["a", "b"] for _ in range(10)] + [["x", "y", "z"], ["1", "2", "3"]]
    _write_xlsx(path, {"S": rows})
    section = _only_section(path)
    assert "not determined confidently" in section.text
    assert "assuming the first row is the header" in section.text


def test_rendered_sheet_has_explicit_1based_row_number_column(tmp_path):
    path = tmp_path / "row_numbers.xlsx"
    _write_xlsx(path, {"S": [
        ["Name", "Value"],
        ["x", 1],
        ["y", 2],
    ]})
    section = _only_section(path)
    assert re.search(r"\|\s*#\s*\|\s*Name", section.text)
    assert re.search(r"\|\s*1\s*\|\s*x", section.text)
    assert re.search(r"\|\s*2\s*\|\s*y", section.text)


def test_no_identifiable_header_still_rendered(tmp_path):
    # A sheet with no non-empty cell has no identifiable header: it is still
    # rendered, never dropped, never raises, and says what was assumed.
    path = tmp_path / "empty_sheet.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame().to_excel(writer, sheet_name="Blank", index=False, header=False)
    sections = parse_xlsx(str(path))
    assert any(s.section_title == "Blank" for s in sections)
    section = next(s for s in sections if s.section_title == "Blank")
    assert section.text.strip()
    assert "no header row could be identified" in section.text
    assert "assuming the first row is the header" in section.text

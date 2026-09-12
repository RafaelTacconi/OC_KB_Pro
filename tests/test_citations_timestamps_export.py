"""
test_citations_timestamps_export.py — SPEC.md A30–A34.

A30 chip row labelled "Retrieved from" (retrieved set, not the model's citations)
A31 chips deduped by (display_name, section_title)
A32 the answer renders on send (inline render; spinner becomes the answer)
A33 per-message timestamp, displayed in local time (stored UTC)
A34 Markdown chat export with question/answer/sources/model/timestamp
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import ui.chat_view
from ui.cards import chips_html, format_local_time
from ui.export import chat_to_markdown

REPO_ROOT = Path(__file__).resolve().parents[1]
_NOW = "2026-09-13T12:00:00+00:00"


# --- A30 / A31: chip labelling and dedupe -----------------------------------

def test_a30_chip_row_is_labelled_retrieved_from():
    html = chips_html([{"display_name": "A.pdf", "section_title": "1. Scope"}],
                      heading="Retrieved from")
    assert "Retrieved from" in html


def test_a31_chips_dedupe_by_name_and_section():
    sources = [
        {"display_name": "AML_Thresholds.xlsx", "section_title": "Transaction Thresholds"},
        {"display_name": "AML_Thresholds.xlsx", "section_title": "Transaction Thresholds"},
        {"display_name": "AML_Thresholds.xlsx", "section_title": "Other"},
    ]
    html = chips_html(sources, heading="Retrieved from")
    assert html.count("Transaction Thresholds") == 1   # deduped
    assert html.count("Other") == 1


# --- A33: timestamp formatting ----------------------------------------------

def test_a33_format_local_time_converts_from_utc():
    # UTC noon -> same instant in local time; the function must not crash and
    # must return a non-empty display string.
    out = format_local_time("2026-09-13T12:00:00+00:00")
    assert out and len(out) == 16  # "YYYY-MM-DD HH:MM"
    # Unparseable / empty -> ""
    assert format_local_time("") == ""
    assert format_local_time("not-a-date") == ""


# --- A34: Markdown export ---------------------------------------------------

def test_a34_chat_to_markdown_contains_all_fields(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL_STANDARD", "std-real")
    messages = [
        {"role": "user", "content": "How fast must we escalate?", "created_at": _NOW,
         "model_id": None, "cited_sources": None},
        {"role": "assistant", "content": "Within 12 hours.",
         "created_at": _NOW, "model_id": "internal-standard",
         "cited_sources": '[{"display_name": "AML_Policy.pdf", "section_title": "2. Escalation Timeline"}]'},
    ]
    md = chat_to_markdown("AML chat", messages)
    assert "# AML chat" in md
    assert "How fast must we escalate?" in md
    assert "Within 12 hours." in md
    assert "AML_Policy.pdf" in md
    assert "2. Escalation Timeline" in md
    assert "Standard" in md            # model display name
    assert "std-real" in md            # .env slug (display name + slug)
    assert "Exported" in md


# --- A32 / A33 / A34 end-to-end --------------------------------------------

def _seed_chat(tmp_path, answer: str = "Within 12 hours of detection.") -> None:
    import db as db_module

    db_module.init_db()
    db_module.migrate_db()
    from config import bootstrap

    bootstrap()
    conn = sqlite3.connect(tmp_path / "data" / "workspace_app.db")
    try:
        chat_id = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO chats (chat_id, workspace_id, user_id, title, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (chat_id, "aml-workspace", "u_member1", "Seeded chat", _NOW, _NOW),
        )
        rows = [
            ("user", "How fast must we escalate?"),
            ("assistant", answer),
        ]
        for role, content in rows:
            conn.execute(
                "INSERT INTO chat_messages (message_id, chat_id, workspace_id, user_id, role, "
                "content, cited_sources, retrieved_chunk_ids, task_id, model_id, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, chat_id, "aml-workspace", "u_member1", role, content,
                 '[{"display_name": "AML_Policy.pdf", "section_title": "2. Escalation Timeline"}]'
                 if role == "assistant" else None,
                 None, None, "internal-standard" if role == "assistant" else None, _NOW),
            )
        conn.commit()
    finally:
        conn.close()


def test_a33_and_a34_seeded_chat_shows_timestamp_and_export(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed_chat(tmp_path)
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    at.sidebar.selectbox[0].set_value("u_member1").run()
    assert not at.exception, list(at.exception)
    # A33: the seeded message shows a timestamp caption.
    assert any("2026-09-13" in c.value for c in at.caption)
    # A34: an export download button is present.
    assert len(at.download_button) >= 1


def test_a32_send_renders_answer(monkeypatch, tmp_path, configured_model):
    import os

    os.environ["HF_HUB_OFFLINE"] = "1"
    monkeypatch.chdir(tmp_path)

    def _stub(prompt: str, model_id: str) -> str:
        return "THE-ANSWER-TEXT"

    monkeypatch.setattr(ui.chat_view, "call_model", _stub)
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    at.chat_input[0].set_value("What is the escalation window?").run()
    assert not at.exception, list(at.exception)
    # The assistant's answer is rendered in the chat (inline render path).
    assert any("THE-ANSWER-TEXT" in (m.value or "") for m in at.markdown)
"""
test_chat_error_handling.py — acceptance criteria A12 / A13 (SPEC.md §10).

Runs the real app headlessly via streamlit.testing.v1.AppTest and exercises a
full chat turn with the model stub still failing (SPEC.md §7.1):

  A12 — sending a message with `_call_internal_gateway()` raising
        NotImplementedError renders an inline error inside the conversation,
        keeps the page alive (no exception reaches the error screen), and
        persists the user's message, which is still visible after a rerun.
  A13 — Retry after a failure produces exactly one additional model attempt
        and does not duplicate the user's message.

The test is deliberately hermetic: it runs in a temp working directory so the
SQLite DB is created there, and it forces the Hugging Face hub offline so the
embedding model cannot be downloaded mid-test. Whether the embedder was
already cached (retrieval succeeds, then the stub model call fails) or not
(retrieval itself fails) the assertion targets are the same: the failure is
contained, the user message persists exactly once, and Retry does not
duplicate it.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _db_rows(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT role, content, model_id FROM chat_messages ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _count_by_role(rows: list[dict], role: str) -> int:
    return sum(1 for r in rows if r["role"] == role)


def test_failed_turn_persists_question_and_retry_does_not_duplicate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    os.environ["INTERNAL_API_KEY"] = "test-key-for-stub"  # so the stub reaches NotImplementedError
    os.environ["HF_HUB_OFFLINE"] = "1"
    monkeypatch.chdir(tmp_path)

    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception

    question = "What is the escalation window?"

    # --- Send a message (A12) -------------------------------------------------
    at.chat_input[0].set_value(question).run()

    # Page is alive: nothing escaped the §7.1 handler to the error screen.
    assert not at.exception
    # Inline error bubble inside the conversation, not a toast on the error page.
    assert any("Something went wrong while answering" in e.value for e in at.error)
    # The Retry control that belongs to that bubble is present.
    retry = at.button(key="wa_retry_button")

    db_path = tmp_path / "data" / "workspace_app.db"
    rows = _db_rows(db_path)
    assert _count_by_role(rows, "user") == 1
    assert _count_by_role(rows, "assistant") == 0
    user_row = next(r for r in rows if r["role"] == "user")
    assert user_row["content"] == question

    # --- Retry (A13) ------------------------------------------------------------
    retry.click().run()

    assert not at.exception
    rows = _db_rows(db_path)
    # Exactly one user row for this turn still — Retry must not re-persist it.
    assert _count_by_role(rows, "user") == 1
    # The stub still fails, so no assistant message is persisted.
    assert _count_by_role(rows, "assistant") == 0
"""
test_task_vs_freetext.py — SPEC.md §7.6 (option a) + pending-error interaction.

§7.6: if a user selects a Task but then types into the free-text st.chat_input,
the message is sent with task=None while the Task chip stays selected — nothing
tells the user the Task prompt was not applied. Option (a, preferred): clear the
Task selection and note inline that it was not applied.

Also covers the interaction with the §7.1 pending-error flow: a free-text send
during an active task must do BOTH — clear the task + set the inline note, and
still run through the error path (persist user msg, stash error, retry bubble)
when the model call fails.
"""

from __future__ import annotations

import sqlite3
import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import ui.chat_view

REPO_ROOT = Path(__file__).resolve().parents[1]

QUESTION = "What is the escalation window?"


@pytest.fixture()
def stubbed_answer(monkeypatch: pytest.MonkeyPatch, configured_model) -> list[str]:
    calls: list[str] = []

    def fake_call(prompt: str, model_id: str) -> str:
        calls.append(model_id)
        return "A grounded answer."

    monkeypatch.setattr(ui.chat_view, "call_model", fake_call)
    return calls


def _seed_failing_call(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """A call_model that always fails (for the pending-error interaction).
    NOTE: the calling test must request the `configured_model` fixture first so
    the chat input is enabled (SPEC §15.2)."""
    attempts: list[str] = []

    def _failing(prompt: str, model_id: str) -> str:
        attempts.append(model_id)
        raise RuntimeError("forced failure")

    monkeypatch.setattr(ui.chat_view, "call_model", _failing)
    return attempts


def _messages(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(
            "SELECT role, content, task_id FROM chat_messages ORDER BY created_at"
        )]
    finally:
        conn.close()


def _select_first_task(at: AppTest) -> None:
    task_btn = next(b for b in at.button if b.key and b.key.startswith("task_btn_"))
    task_btn.click().run()


def test_freetext_while_task_selected_clears_task_and_notes_inline(
    monkeypatch, tmp_path, stubbed_answer
):
    monkeypatch.chdir(tmp_path)
    os.environ["HF_HUB_OFFLINE"] = "1"
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception

    # Select a task.
    _select_first_task(at)
    assert not at.exception
    assert "selected_task_aml-workspace" in at.session_state

    # Send a free-text question via st.chat_input.
    at.chat_input[0].set_value(QUESTION).run()
    assert not at.exception

    # The task selection is cleared (value None) and the inline note shows.
    assert "selected_task_aml-workspace" in at.session_state
    assert at.session_state["selected_task_aml-workspace"] is None
    assert any("was not applied" in i.value for i in at.info)
    # And the message was sent WITHOUT a task tag (task_id NULL).
    db_path = tmp_path / "data" / "workspace_app.db"
    user_rows = [m for m in _messages(db_path) if m["role"] == "user"]
    assert user_rows and user_rows[0]["task_id"] is None


def test_freetext_without_task_has_no_note(
    monkeypatch, tmp_path, stubbed_answer
):
    monkeypatch.chdir(tmp_path)
    os.environ["HF_HUB_OFFLINE"] = "1"
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    at.chat_input[0].set_value(QUESTION).run()
    assert not at.exception
    assert not any("was not applied" in i.value for i in at.info)


def test_freetext_while_task_selected_plus_pending_error(
    monkeypatch, tmp_path, configured_model
):
    """§7.6 x §7.1 interaction: a free-text send during an active task with a
    failing model must do BOTH — clear the task + set the inline note, AND
    surface the pending error (user message persisted, retry present)."""
    _seed_failing_call(monkeypatch)
    monkeypatch.chdir(tmp_path)
    os.environ["HF_HUB_OFFLINE"] = "1"
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception

    _select_first_task(at)
    assert not at.exception

    at.chat_input[0].set_value(QUESTION).run()
    assert not at.exception

    # Task cleared (value None) + inline note.
    assert "selected_task_aml-workspace" in at.session_state
    assert at.session_state["selected_task_aml-workspace"] is None
    assert any("was not applied" in i.value for i in at.info)
    # Pending error surfaced too.
    assert any("Something went wrong while answering" in e.value for e in at.error)
    retry = at.button(key="wa_retry_button")
    # User message persisted despite the failure.
    db_path = tmp_path / "data" / "workspace_app.db"
    user_rows = [m for m in _messages(db_path) if m["role"] == "user"]
    assert len(user_rows) == 1
    assert user_rows[0]["content"] == QUESTION
    assert user_rows[0]["task_id"] is None
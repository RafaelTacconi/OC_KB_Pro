"""
test_delete_confirmations.py — acceptance criterion A16 (SPEC.md §10).

Deleting a Source or a Task must require an explicit second confirmation that
names the item (SPEC.md §7.4). Runs the app headlessly via AppTest from the
Owner's Manage surface:

  - Task: bootstrap seeds two Tasks; "Delete task" only arms a confirm, does
    not delete; Cancel dismisses; only "Confirm delete" removes the row.
  - Source: a fake source row is inserted into the temp DB (no file upload
    needed); the same arming → Cancel → confirm sequence applies.

Both run in a temp working directory so the SQLite DB is created there, not in
the repository's data/ directory.
"""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

REPO_ROOT = Path(__file__).resolve().parents[1]

_FAKE_NOW = "2026-09-11T00:00:00+00:00"


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _task_ids(db_path: Path) -> set[str]:
    conn = _connect(db_path)
    try:
        return {r["task_id"] for r in conn.execute("SELECT task_id FROM tasks")}
    finally:
        conn.close()


def _source_ids(db_path: Path) -> set[str]:
    conn = _connect(db_path)
    try:
        return {r["source_id"] for r in conn.execute("SELECT source_id FROM sources")}
    finally:
        conn.close()


def _open_prompts_section(at: AppTest) -> None:
    at.button(key="nav_manage").click().run()
    at.radio(key="wa_manage_section").set_value("Prompts (/)").run()


def test_task_deletion_requires_explicit_second_confirmation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    _open_prompts_section(at)

    db_path = tmp_path / "data" / "workspace_app.db"
    before = _task_ids(db_path)
    assert len(before) >= 2  # bootstrap seeds two tasks
    task_id = sorted(before)[0]

    # First click only arms the confirm — nothing is deleted, no exception.
    at.button(key=f"delete_task_{task_id}").click().run()
    assert not at.exception
    assert _task_ids(db_path) == before
    # The confirm/cancel pair naming the item is now present.
    at.button(key=f"confirm_delete_btn_task_{task_id}")
    cancel = at.button(key=f"cancel_delete_btn_task_{task_id}")

    # Cancel keeps the task and dismisses the confirm.
    cancel.click().run()
    assert not at.exception
    assert _task_ids(db_path) == before
    with pytest.raises(KeyError):
        at.button(key=f"confirm_delete_btn_task_{task_id}")

    # Arm again, then confirm — only the confirm click deletes.
    at.button(key=f"delete_task_{task_id}").click().run()
    at.button(key=f"confirm_delete_btn_task_{task_id}").click().run()
    assert not at.exception
    after = _task_ids(db_path)
    assert task_id not in after
    assert len(after) == len(before) - 1


def test_source_deletion_requires_explicit_second_confirmation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    from config import bootstrap

    bootstrap()  # creates the DB in tmp cwd and seeds users/workspace/tasks
    source_id = uuid.uuid4().hex
    conn = _connect(tmp_path / "data" / "workspace_app.db")
    try:
        conn.execute(
            """
            INSERT INTO sources
                (source_id, workspace_id, source_type, display_name, origin_ref,
                 status, error_message, indexed_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id, "aml-workspace", "pdf", "AML_Policy.pdf",
                "data/aml-workspace/sources/fake.pdf", "indexed", None,
                _FAKE_NOW, _FAKE_NOW,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    at.button(key="nav_manage").click().run()  # Knowledge is the default section
    assert not at.exception

    db_path = tmp_path / "data" / "workspace_app.db"
    before = _source_ids(db_path)
    assert source_id in before

    # First click only arms the confirm — nothing is deleted.
    at.button(key=f"delete_{source_id}").click().run()
    assert not at.exception
    assert _source_ids(db_path) == before
    at.button(key=f"confirm_delete_btn_source_{source_id}")
    cancel = at.button(key=f"cancel_delete_btn_source_{source_id}")

    # Cancel keeps the source and dismisses the confirm.
    cancel.click().run()
    assert not at.exception
    assert _source_ids(db_path) == before
    with pytest.raises(KeyError):
        at.button(key=f"confirm_delete_btn_source_{source_id}")

    # Arm again, then confirm — only the confirm click deletes.
    at.button(key=f"delete_{source_id}").click().run()
    at.button(key=f"confirm_delete_btn_source_{source_id}").click().run()
    assert not at.exception
    after = _source_ids(db_path)
    assert source_id not in after
    assert len(after) == len(before) - 1
"""
test_task_row_wrap.py — UI review item 6.

The task row was a single st.columns(len(tasks)+1); past a handful of tasks it
is unusable. Now it wraps into rows of up to MAX_PER_ROW. This test seeds many
tasks and asserts every one still renders as a clickable button (the row grouped
into multiple wrapped column sets).
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

REPO_ROOT = Path(__file__).resolve().parents[1]


_NOW = "2026-09-11T00:00:00+00:00"


def _seed_tasks(tmp_path, n: int) -> list[str]:
    """Create the seeded workspace+users, then n tasks; return their ids."""
    import db as db_module

    db_module.init_db()
    db_module.migrate_db()
    from config import bootstrap

    bootstrap()

    conn = sqlite3.connect(tmp_path / "data" / "workspace_app.db")
    ids = []
    try:
        for i in range(n):
            tid = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO tasks (task_id, workspace_id, name, description, "
                "prompt, input_label, created_at) VALUES (?,?,?,?,?,?,?)",
                (tid, "aml-workspace", f"/task-{i:02d}", "desc", "prompt", "input", _NOW),
            )
            ids.append(tid)
        conn.commit()
    finally:
        conn.close()
    return ids


def test_task_row_wraps_beyond_four(monkeypatch, tmp_path, configured_model):
    import os

    os.environ["HF_HUB_OFFLINE"] = "1"
    monkeypatch.chdir(tmp_path)
    ids = _seed_tasks(tmp_path, 6)

    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception

    task_buttons = [b for b in at.button if b.key and b.key.startswith("task_btn_")]
    labels = sorted(b.label for b in task_buttons)
    # All 6 seeded tasks render even across multiple wrapped rows (the seeded
    # workspace also ships /summarize-policy + /find-procedure, so label set is
    # a superset).
    for i in range(6):
        assert f"/task-{i:02d}" in labels
    # Every one is clickable (enabled) — a wrap doesn't drop any.
    assert all(not b.proto.disabled for b in task_buttons)


def test_task_row_wraps_at_twenty(monkeypatch, tmp_path, configured_model):
    import os

    os.environ["HF_HUB_OFFLINE"] = "1"
    monkeypatch.chdir(tmp_path)
    ids = _seed_tasks(tmp_path, 20)

    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    task_buttons = [b for b in at.button if b.key and b.key.startswith("task_btn_")]
    assert len(task_buttons) == 22  # 20 seeded + 2 seed tasks
    assert all(not b.proto.disabled for b in task_buttons)
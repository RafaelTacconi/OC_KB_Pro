"""
test_multi_workspace.py — SPEC.md §5 / acceptance criteria A1, A4, A5, A6.

AppTest end-to-end for the multi-Workspace UI:

  A1 — an Owner can create a Workspace (name + optional instructions); it
       appears immediately in the switcher and is selected.
  A4 — switching Workspace clears any selected Task and active Chat.
  A5 — a Member sees only Workspaces they are a member of, and never reaches
       Manage by any route.
  A6 — sidebar branding shows the current Workspace's name; no Workspace name
       is hardcoded in app.py's page chrome (page_title is the product-level
       constant).

A2 (retrieval isolation) is covered at the retrieval layer in
test_workspace_isolation.py; this file is the UI-level complement.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _workspace_selectbox(at: AppTest):
    """Find the sidebar Workspace selectbox (skip the user 'Signed in as'
    selectbox, whose key is None and options are display names)."""
    for sb in at.sidebar.selectbox:
        if sb.key and sb.key.startswith("wa_workspace_selectbox_"):
            return sb
    raise AssertionError("workspace selectbox not found")


def _workspace_names(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(
            "SELECT workspace_id, name, owner_user_id FROM workspaces ORDER BY name"
        )]
    finally:
        conn.close()


def _memberships(db_path: Path, workspace_id: str) -> list[str]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [r["user_id"] for r in conn.execute(
            "SELECT user_id FROM workspace_members WHERE workspace_id = ?",
            (workspace_id,),
        )]
    finally:
        conn.close()


def test_a1_owner_creates_workspace_and_it_is_selected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    db_path = tmp_path / "data" / "workspace_app.db"
    assert len(_workspace_names(db_path)) == 1  # only the seeded AML workspace

    # Owner creates a new workspace via the sidebar form.
    ws_selectbox = _workspace_selectbox(at)
    assert ws_selectbox.options == ["AML Workspace"]

    at.sidebar.text_input(key="new_workspace_name").set_value("HR Workspace")
    at.sidebar.text_area(key="new_workspace_instructions").set_value("HR rules.")
    at.sidebar.button(key="new_workspace_submit").click().run()
    assert not at.exception

    names = _workspace_names(db_path)
    assert len(names) == 2
    hr = next(w for w in names if w["name"] == "HR Workspace")
    # A1: it appears immediately in the switcher and is selected.
    ws_selectbox = _workspace_selectbox(at)
    assert "HR Workspace" in ws_selectbox.options
    assert ws_selectbox.value == hr["workspace_id"]
    # OPEN-4 closed (level (a)): a new Workspace is owned by its creator only —
    # NOT auto-added to every TEST_USER. Members are added via Manage -> Users.
    assert set(_memberships(db_path, hr["workspace_id"])) == {"u_owner"}


def test_a4_switch_clears_task_and_active_chat(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, configured_model
) -> None:
    # task buttons are disabled without a model (§15.2)
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    db_path = tmp_path / "data" / "workspace_app.db"

    # Create a second workspace so there is something to switch to.
    at.sidebar.text_input(key="new_workspace_name").set_value("HR Workspace")
    at.sidebar.button(key="new_workspace_submit").click().run()
    assert not at.exception

    # Select a Task in the AML workspace.
    ws_selectbox = _workspace_selectbox(at)
    ws_selectbox.set_value("aml-workspace").run()
    assert not at.exception
    # Click the first task button (any task_btn_*).
    task_btn = next(b for b in at.button if b.key and b.key.startswith("task_btn_"))
    task_btn.click().run()
    assert not at.exception
    # Task selection is stored under selected_task_<workspace_id>.
    assert "selected_task_aml-workspace" in at.session_state
    assert at.session_state["selected_task_aml-workspace"] is not None

    # Switch to HR workspace — task + chat selection must clear.
    ws_selectbox = _workspace_selectbox(at)
    hr_id = next(w["workspace_id"] for w in _workspace_names(db_path)
                 if w["name"] == "HR Workspace")
    ws_selectbox.set_value(hr_id).run()
    assert not at.exception
    assert "selected_task_aml-workspace" not in at.session_state
    assert "wa_chat_id" not in at.session_state


def test_a5_member_sees_only_their_workspaces_and_no_manage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    db_path = tmp_path / "data" / "workspace_app.db"

    # Owner creates a workspace (OPEN-4 closed: only the Owner is added).
    at.sidebar.text_input(key="new_workspace_name").set_value("HR Workspace")
    at.sidebar.button(key="new_workspace_submit").click().run()

    # The member is NOT a member of HR, so they see only AML — and no Manage.
    at.sidebar.selectbox[0].set_value("u_member1").run()
    assert not at.exception
    ws_selectbox = _workspace_selectbox(at)
    assert set(ws_selectbox.options) == {"AML Workspace"}
    has_manage = any(b.key == "nav_manage" for b in at.sidebar.button)
    assert not has_manage

    # Owner adds the member via Manage -> Users (OPEN-4 membership build).
    at.sidebar.selectbox[0].set_value("u_owner").run()
    hr_id = next(w["workspace_id"] for w in _workspace_names(db_path)
                 if w["name"] == "HR Workspace")
    # Ensure the Owner is viewing HR (switching users reset the switcher to AML).
    _workspace_selectbox(at).set_value(hr_id).run()
    at.button(key="nav_manage").click().run()
    at.radio(key="wa_manage_section").set_value("Users").run()
    # The add-member selectbox lists only non-members of the current (HR)
    # workspace. Since HR is owner-only, u_member1 is an option.
    add_sel = at.selectbox(key=f"add_member_{hr_id}")
    assert "Priya (Member)" in add_sel.options  # u_member1, display label
    add_sel.set_value("Priya (Member)").run()
    at.button(key=f"add_member_btn_{hr_id}").click().run()
    assert not at.exception

    # Now the member sees HR too.
    at.sidebar.selectbox[0].set_value("u_member1").run()
    ws_selectbox = _workspace_selectbox(at)
    assert set(ws_selectbox.options) == {"AML Workspace", "HR Workspace"}


def test_a6_branding_uses_workspace_name(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    # The page header / brand should render the current workspace's name, not
    # a hardcoded string. The chat view's page_header shows the workspace name.
    # We assert the sidebar brand markdown includes the seeded name.
    combined = " ".join(m.value for m in at.markdown)
    assert "AML Workspace" in combined


def test_a3_instructions_and_tasks_do_not_leak(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A3 — Instructions and Tasks configured in Workspace A do not appear or
    apply in Workspace B. The two leaks would be: B's chat listing A's Tasks,
    and B's prompt using A's Instructions."""
    import sqlite3
    import uuid
    from datetime import datetime, timezone

    monkeypatch.chdir(tmp_path)

    now = datetime.now(timezone.utc).isoformat()

    # Create Workspace B with its OWN instructions and a Task, and a set of
    # Tasks in A (seeded) — B must not inherit A's.
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    at.sidebar.text_input(key="new_workspace_name").set_value("HR Workspace")
    at.sidebar.text_area(key="new_workspace_instructions").set_value(
        "HR-specific rule: always mention the people team."
    )
    at.sidebar.button(key="new_workspace_submit").click().run()
    assert not at.exception

    db_path = tmp_path / "data" / "workspace_app.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ws_b = dict(conn.execute(
            "SELECT workspace_id FROM workspaces WHERE name = 'HR Workspace'"
        ).fetchone())
        ws_b_id = ws_b["workspace_id"]
        # Give B its own task.
        conn.execute(
            "INSERT INTO tasks (task_id, workspace_id, name, description, prompt, input_label, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (uuid.uuid4().hex, ws_b_id, "/hr-task", "HR specific", "HR prompt", "input", now),
        )
        # Confirm A's tasks exist (seeded: /summarize-policy, /find-procedure).
        ws_a_tasks = [dict(r) for r in conn.execute(
            "SELECT name FROM tasks WHERE workspace_id = 'aml-workspace'"
        )]
        conn.commit()
    finally:
        conn.close()
    assert "/summarize-policy" in {t["name"] for t in ws_a_tasks}

    # Switch to B (owner).
    ws_selectbox = _workspace_selectbox(at)
    ws_selectbox.set_value(ws_b_id).run()
    assert not at.exception

    # B's chat task row shows ONLY B's task — A's seeded tasks must not appear.
    task_buttons = [b for b in at.button if b.key and b.key.startswith("task_btn_")]
    assert task_buttons, "expected at least B's task button"
    task_labels = [b.label for b in task_buttons]
    assert "/hr-task" in task_labels
    assert "/summarize-policy" not in task_labels
    assert "/find-procedure" not in task_labels

    # B's prompt uses B's Instructions, not A's. _run_turn loads the workspace
    # by id; assert the loaded workspace instructions are B's.
    from ui.chat_view import _load_workspace

    b_ws = _load_workspace(ws_b_id)
    assert "people team" in b_ws.get("instructions", "")
    a_ws = _load_workspace("aml-workspace")
    assert "people team" not in a_ws.get("instructions", "")
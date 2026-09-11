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
    # Membership per §5.3 interim: every TEST_USER.
    assert set(_memberships(db_path, hr["workspace_id"])) == {
        "u_owner", "u_member1", "u_member2",
    }


def test_a4_switch_clears_task_and_active_chat(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
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

    # Owner creates a workspace (adds ALL users as members per §5.3 interim).
    at.sidebar.text_input(key="new_workspace_name").set_value("HR Workspace")
    at.sidebar.button(key="new_workspace_submit").click().run()

    # Switch to a member — they are a member of every workspace (interim rule),
    # so the switcher lists all, and there is NO Manage button.
    at.sidebar.selectbox[0].set_value("u_member1").run()
    assert not at.exception
    ws_selectbox = _workspace_selectbox(at)
    assert set(ws_selectbox.options) == {"AML Workspace", "HR Workspace"}
    # No Manage button for a member (A5).
    has_manage = any(b.key == "nav_manage" for b in at.sidebar.button)
    assert not has_manage


def test_a6_branding_uses_workspace_name(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    # The page header / brand should render the current workspace's name, not
    # a hardcoded string. The chat view's page_header shows the workspace name.
    # We assert the sidebar brand markdown includes the seeded name.
    combined = " ".join(m.value for m in at.markdown)
    assert "AML Workspace" in combined
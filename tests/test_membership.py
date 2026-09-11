"""
test_membership.py — OPEN-4 closed by build (level (a)): per-Workspace
membership management.

The Owner can add/remove members per Workspace from Manage -> Users. The
Workspace Owner cannot be removed. Membership is enforced on BOTH the switcher
(a Member only sees Workspaces they belong to) and, by construction, retrieval
(chats/sources remain scoped to workspace_id regardless of membership).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _workspace_selectbox(at: AppTest):
    for sb in at.sidebar.selectbox:
        if sb.key and sb.key.startswith("wa_workspace_selectbox_"):
            return sb
    raise AssertionError("workspace selectbox not found")


def test_owner_can_remove_member_and_member_loses_access(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception

    # Owner goes to Manage -> Users (AML-workspace is the active one).
    at.button(key="nav_manage").click().run()
    at.radio(key="wa_manage_section").set_value("Users").run()

    # Remove u_member2 (Sam) from AML.
    at.button(key="remove_member_aml-workspace_u_member2").click().run()
    assert not at.exception

    # Switch to the removed member: AML is gone from their switcher.
    at.sidebar.selectbox[0].set_value("u_member2").run()
    assert not at.exception
    # They had only AML; removing it leaves them with NO workspace, so no
    # workspace switcher renders at all.
    assert not any(
        sb.key and sb.key.startswith("wa_workspace_selectbox_") for sb in at.sidebar.selectbox
    ), "removed member must not see the workspace switcher"


def test_owner_cannot_be_removed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    at.button(key="nav_manage").click().run()
    at.radio(key="wa_manage_section").set_value("Users").run()

    # The owner row has no enabled Remove control (disabled).
    remove_btn = at.button(key="remove_member_aml-workspace_u_owner")
    assert remove_btn.proto.disabled


def test_added_member_reaches_workspace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    # Owner removes Sam, then re-adds via the add-member control.
    at.button(key="nav_manage").click().run()
    at.radio(key="wa_manage_section").set_value("Users").run()
    at.button(key="remove_member_aml-workspace_u_member2").click().run()
    at.selectbox(key="add_member_aml-workspace").set_value("Sam (Member)").run()
    at.button(key="add_member_btn_aml-workspace").click().run()
    assert not at.exception

    # Sam is back: sees AML again.
    at.sidebar.selectbox[0].set_value("u_member2").run()
    assert not at.exception
    ws = _workspace_selectbox(at)
    assert "AML Workspace" in ws.options
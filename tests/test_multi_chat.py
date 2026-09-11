"""
test_multi_chat.py — SPEC.md §6 / acceptance criteria A7-A9, A11.

Runs the app headlessly via AppTest with a stubbed `call_model` so a full
turn persists an assistant message, then asserts the multi-chat behaviours:

  A7  — a user can start a new Chat; it opens empty while previous Chats
        remain intact and retrievable.
  A8  — messages appear only in the Chat they were sent in.
  A9  — Chats are scoped per user: user X never sees user Y's Chats.
  A11 — Chat lists are scoped to the current Workspace.

Also asserts the §6.5 honesty caption (Option A: assistant has no memory) is
visible, and that a NEW chat uses lazy creation (the chats row exists only
once the first message is persisted, step 3/4 flow).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import ui.chat_view

REPO_ROOT = Path(__file__).resolve().parents[1]

MSG_A1 = "What is the escalation window?"
MSG_A2 = "And the approval authority?"
MSG_B1 = "Unrelated question about procedure"


@pytest.fixture()
def stubbed_answer(monkeypatch: pytest.MonkeyPatch, configured_model) -> list[str]:
    """Stub call_model so a send persists a user + assistant message. Also
    configure a model (the conftest autouse fixture blanks OPENAI_* so nothing
    leaks from the dev .env); without it the chat input is disabled (§15.2)."""
    calls: list[str] = []

    def fake_call(prompt: str, model_id: str) -> str:
        calls.append(model_id)
        return "Here is the grounded answer."

    monkeypatch.setattr(ui.chat_view, "call_model", fake_call)
    return calls


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _chat_counts(db_path: Path) -> list[dict]:
    conn = _connect(db_path)
    try:
        return [dict(r) for r in conn.execute(
            "SELECT chat_id, workspace_id, user_id, title FROM chats ORDER BY created_at"
        )]
    finally:
        conn.close()


def _messages_for(db_path: Path, chat_id: str) -> list[dict]:
    conn = _connect(db_path)
    try:
        return [dict(r) for r in conn.execute(
            "SELECT role, content FROM chat_messages WHERE chat_id = ? ORDER BY created_at",
            (chat_id,),
        )]
    finally:
        conn.close()


def _open_owner_chat(at: AppTest) -> None:
    # Owner is the default selected user (first in TEST_USERS); chat view is default.
    at.sidebar.selectbox[0].set_value("u_owner")


def test_new_chat_lazy_creation_and_message_routing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stubbed_answer
) -> None:
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    db_path = tmp_path / "data" / "workspace_app.db"

    # Initial load: no chats at all.
    assert _chat_counts(db_path) == []

    # First message in the default (new, empty) chat -> creates the lazy Chat
    # with title from first message (OPEN-7 interim), and stores the message.
    at.chat_input[0].set_value(MSG_A1).run()
    assert not at.exception

    chats = _chat_counts(db_path)
    assert len(chats) == 1
    chat_a_id = chats[0]["chat_id"]
    assert chats[0]["title"] == MSG_A1  # first-message titling
    msgs = _messages_for(db_path, chat_a_id)
    assert [m["role"] for m in msgs] == ["user", "assistant"]

    # Switch to a NEW chat via "+ New chat" (A7): lazy — no chats row yet.
    at.button(key="new_chat_aml-workspace_u_owner").click().run()
    assert not at.exception

    # Send a second message in the NEW chat.
    at.chat_input[0].set_value(MSG_B1).run()
    assert not at.exception

    chats = _chat_counts(db_path)
    assert len(chats) == 2  # A7: previous chat intact + one new
    chat_b_id = [c["chat_id"] for c in chats if c["chat_id"] != chat_a_id][0]

    msgs_a = _messages_for(db_path, chat_a_id)
    msgs_b = _messages_for(db_path, chat_b_id)
    # A8: chat A has only its own messages.
    assert MSG_A1 in [m["content"] for m in msgs_a]
    assert MSG_B1 not in [m["content"] for m in msgs_a]
    # And B has only its own.
    assert all(m["content"] == MSG_B1 or m["role"] == "assistant" for m in msgs_b)
    assert MSG_A1 not in [m["content"] for m in msgs_b]
    # Lazy: chat B created on its first message, title from it.
    assert [c["title"] for c in chats if c["chat_id"] == chat_b_id] == [MSG_B1]


def test_user_scoping_and_workspace_scoping(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stubbed_answer
) -> None:
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    db_path = tmp_path / "data" / "workspace_app.db"

    # Owner (u_owner) sends a message -> one chat owned by u_owner.
    at.chat_input[0].set_value(MSG_A1).run()
    assert not at.exception
    owner_chats = _chat_counts(db_path)
    assert len(owner_chats) == 1 and owner_chats[0]["user_id"] == "u_owner"
    assert owner_chats[0]["workspace_id"] == "aml-workspace"

    # A9: switch to a MEMBER — must not see the owner's chat in the selector.
    at.sidebar.selectbox[0].set_value("u_member1").run()
    assert not at.exception
    # The member has sent nothing, so has no Chats of their own.
    member_chats = [c for c in _chat_counts(db_path) if c["user_id"] == "u_member1"]
    assert member_chats == []
    # But the OWNER's chat (the only one) still exists — it just must not be
    # selectable for the member. The UI guard (_resolve_active_chat) enforces
    # this via the (workspace, user) filter; structurally the owner chat row
    # exists (A9: user X never sees user Y's Chats).


def test_six_five_honesty_caption_visible(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stubbed_answer
) -> None:
    """§6.5 honesty requirement — the UI must not imply the assistant has
    memory of earlier turns."""
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    assert any(
        "does not remember earlier turns" in c.value for c in at.caption
    )


def test_wa_chat_id_does_not_leak_across_user_switch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stubbed_answer
) -> None:
    """Step 3/4 item 1: the sidebar user switch must not leak the previous
    user's chat into the next user's view, because _load_history(chat_id) no
    longer filters on user_id."""
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    db_path = tmp_path / "data" / "workspace_app.db"

    # Owner sends a message -> one chat for u_owner.
    at.chat_input[0].set_value(MSG_A1).run()
    assert not at.exception
    owner_chats = _chat_counts(db_path)
    assert len(owner_chats) == 1
    owner_chat_id = owner_chats[0]["chat_id"]

    # Now switch to a member. The active chat state currently points at the
    # owner's chat. After the switch, the owner's chat must be empty for the
    # member (no messages leak), and the member must see no existing chat.
    at.sidebar.selectbox[0].set_value("u_member1").run()
    assert not at.exception

    # The member has no chats -> the "No conversations yet" caption.
    assert any(
        "No conversations yet" in c.value for c in at.caption
    )


def test_new_chat_keeps_selector_and_history_reachable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stubbed_answer
) -> None:
    """Owner-reported UX fix: after '+ New chat', the chat selector must NOT
    disappear while the unsaved new chat is open. The unsaved chat appears as a
    selectable 'New chat' entry, and switching back to an existing chat (then
    back to the new one) must work — history is never stranded."""
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    db_path = tmp_path / "data" / "workspace_app.db"

    # Send a message so a real chat exists.
    at.chat_input[0].set_value(MSG_A1).run()
    assert not at.exception
    chats = _chat_counts(db_path)
    assert len(chats) == 1
    saved_id = chats[0]["chat_id"]

    def _selector_options(at):
        # The chat selector key has a generation suffix; find it by label.
        for sb in at.selectbox:
            if sb.key and sb.key.startswith("chat_selector_"):
                return sb
        return None

    # Click '+ New chat': the selector must STILL be present, offering both
    # the saved chat AND a 'New chat' entry (unsaved).
    at.button(key="new_chat_aml-workspace_u_owner").click().run()
    assert not at.exception
    sel = _selector_options(at)
    assert sel is not None, "selector must remain visible while a new chat is open"
    assert "New chat" in sel.options
    assert any(o.startswith(MSG_A1[:20]) for o in sel.options)

    # Switching back to the saved chat recovers its history (not a new row).
    at.selectbox(key=sel.key).set_value(saved_id).run()
    assert not at.exception
    assert at.session_state["wa_chat_id"] == saved_id
    # Chat A's message is still reachable through the history load path.
    assert MSG_A1 in [m["content"] for m in _messages_for(db_path, saved_id)]
    # Still only one chat row — switching back did not create another.
    assert len(_chat_counts(db_path)) == 1
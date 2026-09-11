"""
app.py — Streamlit entry point.

Run with: streamlit run app.py

Per spec constraint 6: no real authentication. "Log in" is a selectbox over
the fixed TEST_USERS list (config.py). This is correct and expected for the PoC.

This file only handles page chrome (theme, sidebar, sign-in, navigation) and
routes to the two real views. Business logic stays out of it entirely — see
ui/chat_view.py and ui/owner_view.py for everything that touches the DB,
retrieval, or the model router.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from config import APP_TITLE, DEFAULT_WORKSPACE_ID, TEST_USERS, bootstrap, create_workspace
from models.credentials import api_key_status
from ui.chat_view import render_chat_view
from ui.owner_view import render_owner_view
from ui.pills import ROLE_PILL_MAP, pill, render as render_pill
from ui.theme import inject_tokens, page_icon_path, render_brand

st.set_page_config(
    page_title=APP_TITLE,  # product-level constant — a Workspace isn't known yet (§5.2.3)
    layout="wide",
    page_icon=page_icon_path(),
    initial_sidebar_state="expanded",
)

bootstrap()  # idempotent: init_db + migrate + seed_users + seed_default_workspace

inject_tokens()


def _load_visible_workspaces(user_id: str) -> list[dict]:
    """A user's Workspaces, derived from workspace_members (SPEC §5.3) — never
    from `workspaces` directly, so access control is enforced in one place."""
    from db import get_connection

    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT w.* FROM workspaces w
            JOIN workspace_members wm ON wm.workspace_id = w.workspace_id
            WHERE wm.user_id = ?
            ORDER BY w.name
            """,
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _resolve_workspace(visible: list[dict]) -> str | None:
    """
    Returns the active workspace_id, defaulting to the first visible one on
    startup or when the stored id is no longer visible to the current user
    (§5.2.1 user-switch re-evaluation). Returns None only if the user sees
    no Workspaces at all.
    """
    current = st.session_state.get("wa_workspace_id")
    if current is not None and any(w["workspace_id"] == current for w in visible):
        return current
    if visible:
        st.session_state["wa_workspace_id"] = visible[0]["workspace_id"]
        return visible[0]["workspace_id"]
    return None


def _render_workspace_switcher(current_user: dict) -> str | None:
    """
    §5.2.1 — the Workspace switcher, below the user selectbox and above
    navigation. Selection persists in wa_workspace_id. Switching clears the
    old Workspace's selected task and the active Chat (wa_chat_id), then
    reruns.

    The selectbox is keyed by user_id AND a generation counter (wa_ws_gen):
    bumping the counter (on create / programmatic switch) makes Streamlit
    treat it as a NEW widget that re-initializes from `index` — so a newly
    created Workspace actually becomes selected (A1) instead of the widget
    retaining a stale value that fights wa_workspace_id (the Step-5 item-2
    double-answer trap). A manual selection change also bumps the counter.
    """
    visible = _load_visible_workspaces(current_user["user_id"])
    if not visible:
        return None
    labels = {w["workspace_id"]: w["name"] for w in visible}
    options = [w["workspace_id"] for w in visible]
    current_ws = _resolve_workspace(visible)
    if current_ws is None:
        current_ws = options[0]

    st.markdown('<div class="wa-eyebrow">Workspace</div>', unsafe_allow_html=True)
    # Generation counter in the widget key: a keyed Streamlit selectbox retains
    # its previous value across reruns, so a programmatic switch (e.g. a newly
    # created Workspace) would otherwise fight `index` and silently lose. Bumping
    # the counter makes the widget re-initialize from `index`. Intentional — see
    # memory.md "keyed widget ... generation counter"; do not strip it.
    gen = st.session_state.setdefault("wa_ws_gen", 0)
    selected_ws = st.selectbox(
        "Workspace",
        options=options,
        format_func=lambda wid: labels[wid],
        index=options.index(current_ws),
        key=f"wa_workspace_selectbox_{current_user['user_id']}_{gen}",
    )
    if selected_ws != current_ws:
        # User (or a fresh widget) selected a different Workspace. Clear the
        # old Workspace's Task selection and the active Chat so no state leaks
        # across the switch (SPEC §5.2.1), then adopt it and refresh the widget.
        st.session_state.pop(f"selected_task_{current_ws}", None)
        st.session_state.pop("wa_chat_id", None)
        st.session_state["wa_workspace_id"] = selected_ws
        st.session_state["wa_ws_gen"] = gen + 1
        st.rerun()
    return selected_ws


def _render_new_workspace(current_user: dict) -> None:
    """§5.2.2 — Owner-only "+ New Workspace" expander. Name (required) +
    Instructions (optional). Nothing else. Empty names rejected inline."""
    if current_user["role"] != "owner":
        return
    with st.expander("+ New Workspace"):
        with st.form(key="new_workspace_form"):
            ws_name = st.text_input(
                "Name",
                placeholder="e.g. AML, HR, Procurement",
                key="new_workspace_name",
            )
            ws_instructions = st.text_area(
                "Instructions",
                height=120,
                key="new_workspace_instructions",
            )
            created = st.form_submit_button(
                "Create workspace",
                type="primary",
                key="new_workspace_submit",
            )
        if created:
            if not ws_name.strip():
                st.warning("Workspace name cannot be empty.")
            else:
                new_id = create_workspace(
                    ws_name.strip(), ws_instructions, current_user["user_id"]
                )
                st.session_state["wa_workspace_id"] = new_id
                st.session_state.pop("wa_chat_id", None)
                # Bump the switcher generation so the new Workspace is
                # actually selected (A1) rather than the widget retaining its
                # old value.
                st.session_state["wa_ws_gen"] = st.session_state.get("wa_ws_gen", 0) + 1
                st.rerun()


with st.sidebar:
    st.markdown('<div class="wa-eyebrow">Signed in as</div>', unsafe_allow_html=True)
    user_labels = {u["user_id"]: u["display_name"] for u in TEST_USERS}
    selected_user_id = st.selectbox(
        "Signed in as",
        options=[u["user_id"] for u in TEST_USERS],
        format_func=lambda uid: user_labels[uid],
        label_visibility="collapsed",
    )
    current_user = next(u for u in TEST_USERS if u["user_id"] == selected_user_id)
    render_pill(pill(current_user["role"].capitalize(), {
        "Owner": ROLE_PILL_MAP["owner"],
        "Member": ROLE_PILL_MAP["member"],
    }))

    # --- Workspace switcher (SPEC §5.2.1) ----------------------------------
    current_ws = _render_workspace_switcher(current_user)

    # --- Branding (SPEC §5.2.3): dynamic per-Workspace name. ---------------
    if current_ws is not None:
        ws_row = next(
            (w for w in _load_visible_workspaces(current_user["user_id"])
             if w["workspace_id"] == current_ws), {}
        )
        render_brand(ws_row.get("name", "Workspace"), APP_TITLE)
    else:
        render_brand("AI Workspace", APP_TITLE)

    # --- API key expiry (SPEC §14.5) ----------------------------------------
    # Informational only, evaluated once per render. Never blocks anything.
    # OPEN-12 interim: expiring/unknown -> Owners only; expired -> everyone.
    _key_status = api_key_status()
    if _key_status.state == "expired":
        render_pill(pill(
            f"API key expired on {_key_status.expires_on}",
            {"expired": ("red", "\u2715")},
        ))
        st.caption("Answer calls will fail until the API key is renewed.")
    elif _key_status.state == "expiring" and current_user["role"] == "owner":
        render_pill(pill(
            f"API key expires {_key_status.expires_on} "
            f"({_key_status.days_remaining}d)",
            {"expiring": ("orange", "\u26a0")},
        ))
        st.caption("Renew the API key in .env before it expires.")
    elif _key_status.state == "unknown" and current_user["role"] == "owner":
        render_pill(pill(
            "No API key expiry date set",
            {"unknown": ("gray", "\u25cf")},
        ))
        st.caption("Set OPENAI_API_KEY_EXPIRES_ON to get advance warning.")

    # --- New Workspace (Owner only, SPEC §5.2.2) ---------------------------
    _render_new_workspace(current_user)

    st.divider()

    # --- Primary navigation ------------------------------------------------
    st.session_state.setdefault("wa_nav", "Chat")
    is_owner = current_user["role"] == "owner"

    if st.button("Chat", key="nav_chat", use_container_width=True,
                 type="primary" if st.session_state["wa_nav"] == "Chat" else "secondary"):
        st.session_state["wa_nav"] = "Chat"
        st.rerun()

    if is_owner:
        if st.button("Manage", key="nav_manage", use_container_width=True,
                     type="primary" if st.session_state["wa_nav"] == "Manage" else "secondary"):
            st.session_state["wa_nav"] = "Manage"
            st.rerun()
    elif st.session_state["wa_nav"] == "Manage":
        st.session_state["wa_nav"] = "Chat"  # member switched to; Manage isn't theirs

    st.divider()

    with st.expander("About this Workspace"):
        readme_path = Path(__file__).parent / "README.md"
        st.caption(
            "Internal AI Workspace — ask questions grounded in your team's own "
            "documents, or run a predefined task. Owners manage what the AI can "
            "see and how it behaves under **Manage**."
        )
        if readme_path.exists():
            st.caption("Full project notes are in this app's README.md.")

workspace_id = current_ws if current_ws is not None else DEFAULT_WORKSPACE_ID

if st.session_state["wa_nav"] == "Manage" and current_user["role"] == "owner":
    render_owner_view(workspace_id)
else:
    render_chat_view(workspace_id, current_user["user_id"])

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

from config import DEFAULT_WORKSPACE_ID, TEST_USERS, bootstrap
from models.credentials import api_key_status
from ui.chat_view import render_chat_view
from ui.owner_view import render_owner_view
from ui.pills import pill, render as render_pill
from ui.theme import inject_tokens, page_icon_path, render_brand

st.set_page_config(
    page_title="AML Workspace",
    layout="wide",
    page_icon=page_icon_path(),
    initial_sidebar_state="expanded",
)

bootstrap()  # idempotent: init_db + seed_users + seed_default_workspace

inject_tokens()

ROLE_PILL_MAP = {
    "owner": ("green", "\u25c6"),   # ◆
    "member": ("gray", "\u25cf"),   # ●
}

with st.sidebar:
    render_brand("AML Workspace", "AI Workspace")

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

workspace_id = DEFAULT_WORKSPACE_ID  # PoC: single fixed Workspace (Section 4.1)

if st.session_state["wa_nav"] == "Manage" and current_user["role"] == "owner":
    render_owner_view(workspace_id)
else:
    render_chat_view(workspace_id, current_user["user_id"])

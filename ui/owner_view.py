"""
owner_view.py — Workspace setup surface (spec Section 10.1).

Sections: Knowledge, Instructions, Prompts (tasks), Users, Summary.
Per constraint 3 (Section 5): this module calls ingestion.pipeline.ingest_source()
and ingestion.pipeline.delete_source() only — it never imports a parser or
chunker directly.

The Users section is read-only: it reads the existing `users` + `workspace_members`
tables (already seeded by config.py's bootstrap). No schema change and no new
invite/removal mechanism — the PoC's membership is fixed, this just makes it visible.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from db import get_connection, transaction
from config import add_member, remove_member
from ingestion.pipeline import delete_source, ingest_source
from ui.cards import kpi_row
from ui.pills import ROLE_PILL_MAP, pill, render as render_pill
from ui.theme import page_header

SOURCE_TYPE_BY_EXT = {"pdf": "pdf", "docx": "docx", "xlsx": "xlsx"}
UPLOAD_ROOT = Path("data")

SOURCE_STATUS_MAP = {
    "indexed": ("green", "\u25cf"),      # ●
    "processing": ("blue", "\u25d0"),    # ◐
    "pending": ("gray", "\u25cb"),       # ○
    "failed": ("red", "\u2715"),         # ✕
}

SECTIONS = ["Knowledge", "Instructions", "Prompts (/)", "Users", "Summary"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_sources(workspace_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM sources WHERE workspace_id = ? ORDER BY created_at",
            (workspace_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _load_tasks(workspace_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE workspace_id = ? ORDER BY created_at",
            (workspace_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _load_workspace(workspace_id: str) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM workspaces WHERE workspace_id = ?", (workspace_id,)
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def _load_members(workspace_id: str) -> list[dict]:
    """Read-only: workspace_members joined with users. Owner sorts first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT u.user_id, u.display_name, u.role
            FROM workspace_members wm
            JOIN users u ON u.user_id = wm.user_id
            WHERE wm.workspace_id = ?
            ORDER BY (u.role != 'owner'), u.display_name
            """,
            (workspace_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _chunk_count(workspace_id: str) -> int:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM chunks WHERE workspace_id = ?", (workspace_id,)
        ).fetchone()
        return row["n"]
    finally:
        conn.close()


def _render_delete_confirmation(item_label: str, kind: str, entity_id: str) -> bool:
    """
    SPEC §7.4 — two-step delete confirmation. The first click only sets a
    session-state flag keyed by the entity id (confirm_delete_{kind}_{id});
    this renders an explicit "Confirm delete" / "Cancel" pair naming the item.
    Returns True only when the user clicks Confirm delete during this render;
    the caller performs the actual deletion and clears the flag. Cancel clears
    the flag and reruns. The same pattern is used for both Source and Task
    deletion — one confirmation style, as the spec requires.
    """
    st.warning(f"Delete **{item_label}**? This cannot be undone.")
    col_confirm, col_cancel = st.columns(2)
    confirmed = False
    with col_confirm:
        if st.button(
            "Confirm delete",
            key=f"confirm_delete_btn_{kind}_{entity_id}",
            type="primary",
            use_container_width=True,
        ):
            confirmed = True
    with col_cancel:
        if st.button(
            "Cancel",
            key=f"cancel_delete_btn_{kind}_{entity_id}",
            use_container_width=True,
        ):
            st.session_state.pop(f"confirm_delete_{kind}_{entity_id}", None)
            st.rerun()
    return confirmed


# ---------------------------------------------------------------------------------------
# Knowledge
# ---------------------------------------------------------------------------------------

def _render_knowledge_section(workspace_id: str) -> None:
    st.subheader("Knowledge sources")
    st.caption("Files the AI can draw on when answering questions in this Workspace.")

    sources = _load_sources(workspace_id)
    if not sources:
        st.markdown(
            '<div class="wa-empty">No sources uploaded yet — add one below to get started.</div>',
            unsafe_allow_html=True,
        )
    else:
        with st.container(border=True):
            for i, src in enumerate(sources):
                flag_key = f"confirm_delete_source_{src['source_id']}"
                if st.session_state.get(flag_key):
                    if _render_delete_confirmation(
                        src["display_name"], "source", src["source_id"]
                    ):
                        delete_source(src["source_id"])
                        st.session_state.pop(flag_key, None)
                        st.rerun()
                else:
                    cols = st.columns([5, 2, 1], vertical_alignment="center")
                    cols[0].markdown(f"**{src['display_name']}**")
                    # SPEC §15.1 — embedded-image visibility. The count is a
                    # floor (vector diagrams/curve text may not register).
                    img_count = src.get("image_count") or 0
                    if img_count > 0:
                        cols[0].caption(
                            f"{img_count} image{'s' if img_count != 1 else ''} — "
                            "their content is not indexed"
                        )
                    with cols[1]:
                        render_pill(pill(src["status"], SOURCE_STATUS_MAP))
                        if src["status"] == "failed" and src.get("error_message"):
                            st.caption(
                                "Indexing failed — "
                                f"{src['error_message']}"
                            )
                    if cols[2].button("Delete", key=f"delete_{src['source_id']}",
                                       use_container_width=True):
                        st.session_state[flag_key] = True
                        st.rerun()
                if i < len(sources) - 1:
                    st.divider()

    st.markdown("&nbsp;", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("**Add knowledge to this Workspace**")
        uploaded_files = st.file_uploader(
            "Add knowledge to this Workspace",
            type=["pdf", "docx", "xlsx"],
            accept_multiple_files=True,
            key=f"uploader_{workspace_id}",
            label_visibility="collapsed",
        )
        # Processing must be triggered explicitly (Streamlit reruns the whole script
        # on any interaction — an implicit trigger would re-ingest on every rerun).
        process_clicked = st.button(
            "Process uploaded files",
            key=f"process_{workspace_id}",
            type="primary",
            disabled=not uploaded_files,
        )

    if uploaded_files and process_clicked:
        workspace_dir = UPLOAD_ROOT / workspace_id / "sources"
        workspace_dir.mkdir(parents=True, exist_ok=True)

        for f in uploaded_files:
            ext = f.name.rsplit(".", 1)[-1].lower()
            source_type = SOURCE_TYPE_BY_EXT.get(ext)
            if not source_type:
                st.warning(f"Skipping unsupported file type: {f.name}")
                continue

            source_id = uuid.uuid4().hex
            file_path = workspace_dir / f"{source_id}.{ext}"
            file_path.write_bytes(f.getbuffer())

            with transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO sources
                        (source_id, workspace_id, source_type, display_name,
                         origin_ref, status, created_at)
                    VALUES (?, ?, ?, ?, ?, 'pending', ?)
                    """,
                    (source_id, workspace_id, source_type, f.name, str(file_path), _now()),
                )

            with st.status(f"Processing {f.name}...", expanded=True) as status:
                status.update(label="Parsing, chunking, embedding, and indexing...")
                ingest_source(str(file_path), source_type, source_id, workspace_id)

                conn = get_connection()
                try:
                    row = conn.execute(
                        "SELECT status, error_message FROM sources WHERE source_id = ?",
                        (source_id,),
                    ).fetchone()
                finally:
                    conn.close()

                if row["status"] == "indexed":
                    status.update(label=f"Indexed {f.name}", state="complete")
                else:
                    status.update(label=f"Failed: {row['error_message']}", state="error")
        st.rerun()


# ---------------------------------------------------------------------------------------
# Instructions
# ---------------------------------------------------------------------------------------

def _render_instructions_section(workspace_id: str) -> None:
    st.subheader("Workspace instructions")
    st.caption(
        "Plain-text rules for how the AI should behave in this Workspace — applied "
        "to every question and task, invisibly, before the model answers."
    )
    workspace = _load_workspace(workspace_id)
    with st.container(border=True):
        instructions = st.text_area(
            "Instructions",
            value=workspace.get("instructions", ""),
            height=220,
            key=f"instructions_{workspace_id}",
            label_visibility="collapsed",
        )
        if st.button("Save instructions", key=f"save_instructions_{workspace_id}",
                      type="primary"):
            with transaction() as conn:
                conn.execute(
                    "UPDATE workspaces SET instructions = ?, updated_at = ? WHERE workspace_id = ?",
                    (instructions, _now(), workspace_id),
                )
            # §7.8: st.success before st.rerun() would be discarded by the
            # rerun — set a flag rendered after it instead.
            st.session_state["wa_owner_toast"] = "Saved."
            st.rerun()


# ---------------------------------------------------------------------------------------
# Prompts / tasks
# ---------------------------------------------------------------------------------------

def _render_tasks_section(workspace_id: str) -> None:
    st.subheader("Predefined tasks")
    st.caption("Buttons users see above the chat box — each runs a fixed prompt of your choosing.")
    tasks = _load_tasks(workspace_id)

    for task in tasks:
        flag_key = f"confirm_delete_task_{task['task_id']}"
        with st.expander(
            f"{task['name']}  —  {task['description']}",
            key=f"task_expander_{task['task_id']}",
        ):
            with st.form(key=f"edit_task_{task['task_id']}"):
                name = st.text_input("Name", value=task["name"])
                description = st.text_input("Description", value=task["description"])
                prompt = st.text_area("Prompt (task instructions)", value=task["prompt"], height=150)
                input_label = st.text_input("Input label", value=task["input_label"])
                col1, col2 = st.columns(2)
                save = col1.form_submit_button("Save", type="primary",
                                               use_container_width=True,
                                               key=f"save_task_{task['task_id']}")
                delete = col2.form_submit_button("Delete task", use_container_width=True,
                                                 key=f"delete_task_{task['task_id']}")
            if save:
                with transaction() as conn:
                    conn.execute(
                        """
                        UPDATE tasks
                        SET name = ?, description = ?, prompt = ?, input_label = ?
                        WHERE task_id = ?
                        """,
                        (name, description, prompt, input_label, task["task_id"]),
                    )
                # §7.8: flag rendered after the rerun (see instructions save).
                st.session_state["wa_owner_toast"] = "Saved."
                st.rerun()
            if delete:
                # SPEC §7.4 — a form's submit buttons can't host the confirm
                # step (the form resets on submit), so arming only sets a flag;
                # the confirm/cancel pair renders outside the form below.
                st.session_state[flag_key] = True
                st.rerun()
            if st.session_state.get(flag_key):
                if _render_delete_confirmation(task["name"], "task", task["task_id"]):
                    with transaction() as conn:
                        conn.execute("DELETE FROM tasks WHERE task_id = ?", (task["task_id"],))
                    st.session_state.pop(flag_key, None)
                    st.rerun()

    st.markdown("&nbsp;", unsafe_allow_html=True)
    with st.expander("+ New task"):
        with st.form(key=f"new_task_{workspace_id}"):
            name = st.text_input("Name", placeholder="/summarize-policy")
            description = st.text_input("Description", placeholder="What this task does")
            prompt = st.text_area("Prompt (task instructions)", height=150)
            input_label = st.text_input("Input label", placeholder="Paste the case details")
            created = st.form_submit_button("Add task", type="primary")
        if created and name.strip() and prompt.strip():
            with transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO tasks
                        (task_id, workspace_id, name, description, prompt, input_label, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (uuid.uuid4().hex, workspace_id, name, description, prompt, input_label, _now()),
                )
            st.rerun()


# ---------------------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------------------

def _render_users_section(workspace_id: str) -> None:
    st.subheader("Users")
    st.caption(
        "Who can access this Workspace. This PoC uses a fixed test-user list "
        "(constraint 6) — but the OWNER can now add/remove members per "
        "Workspace (OPEN-4 closed). The Owner cannot be removed."
    )
    members = _load_members(workspace_id)
    member_ids = {m["user_id"] for m in members}
    with st.container(border=True):
        for i, member in enumerate(members):
            cols = st.columns([4, 2, 1], vertical_alignment="center")
            cols[0].markdown(f"**{member['display_name']}**")
            with cols[1]:
                render_pill(pill(member["role"].capitalize(), {
                    "Owner": ROLE_PILL_MAP["owner"],
                    "Member": ROLE_PILL_MAP["member"],
                }))
            # Remove (non-owner) members. Owner is not removable.
            can_remove = member["role"] != "owner"
            if cols[2].button(
                "Remove" if can_remove else "",
                key=f"remove_member_{workspace_id}_{member['user_id']}",
                use_container_width=True,
                disabled=not can_remove,
            ):
                remove_member(workspace_id, member["user_id"])
                st.rerun()
            if i < len(members) - 1:
                st.divider()

    # Add a member: pick from TEST_USERS not already in this Workspace.
    from config import TEST_USERS

    available = [u for u in TEST_USERS if u["user_id"] not in member_ids]
    if available:
        with st.container(border=True):
            add_labels = {u["user_id"]: u["display_name"] for u in available}
            sel_user = st.selectbox(
                "Add member",
                options=[u["user_id"] for u in available],
                format_func=lambda uid: add_labels[uid],
                key=f"add_member_{workspace_id}",
            )
            if st.button("Add member", key=f"add_member_btn_{workspace_id}",
                         type="primary"):
                add_member(workspace_id, sel_user)
                st.rerun()
    else:
        st.caption("Every test user is already a member of this Workspace.")


# ---------------------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------------------

def _render_summary_section(workspace_id: str) -> None:
    st.subheader("Summary")
    sources = _load_sources(workspace_id)
    tasks = _load_tasks(workspace_id)
    indexed = [s for s in sources if s["status"] == "indexed"]
    failed = [s for s in sources if s["status"] == "failed"]

    with st.container(border=True):
        kpi_row([
            ("Sources indexed", str(len(indexed))),
            ("Chunks", str(_chunk_count(workspace_id))),
            ("Tasks configured", str(len(tasks))),
        ])

    st.markdown("&nbsp;", unsafe_allow_html=True)

    if failed:
        st.warning(f"{len(failed)} source(s) failed to index — see Knowledge.")
    else:
        render_pill(pill("All sources healthy", {"All sources healthy": ("green", "\u25cf")}))

    last_indexed = max((s["indexed_at"] for s in indexed if s["indexed_at"]), default=None)
    st.caption(f"Last indexed: {last_indexed or 'never'}")
    st.caption(
        "Embedding strategy: short excerpt per chunk (first ~150 words + section "
        "title) is embedded; the full chunk text is sent to the model once "
        "retrieved — see spec Section 8.2a, Option A."
    )


# ---------------------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------------------

_SECTION_RENDERERS = {
    "Knowledge": _render_knowledge_section,
    "Instructions": _render_instructions_section,
    "Prompts (/)": _render_tasks_section,
    "Users": _render_users_section,
    "Summary": _render_summary_section,
}


def render_owner_view(workspace_id: str) -> None:
    workspace = _load_workspace(workspace_id)
    toast = st.session_state.pop("wa_owner_toast", None)
    if toast:
        st.success(toast)
    page_header(workspace.get("name", workspace_id), "Manage")

    st.session_state.setdefault("wa_manage_section", "Knowledge")

    rail_col, content_col = st.columns([1, 4], gap="large")
    with rail_col:
        st.radio(
            "Section",
            options=SECTIONS,
            key="wa_manage_section",
            label_visibility="collapsed",
        )
    with content_col:
        _SECTION_RENDERERS[st.session_state["wa_manage_section"]](workspace_id)

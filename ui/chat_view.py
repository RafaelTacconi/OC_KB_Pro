"""
chat_view.py — the user-facing chat surface (spec Section 10.2, 10.3).

Renders:
  - a model picker (new requirement: user selects which AI model answers)
  - free-form chat (st.chat_input / st.chat_message)
  - a predefined-task picker (st.selectbox-equivalent button row — per constraint 7,
    Section 5, NOT a live "/" autocomplete; Streamlit's st.chat_input does not support
    that natively — streamlit/streamlit#7069 is still open)

This module only calls: retrieval.hybrid_search.hybrid_search(),
prompting.assemble.build_prompt(), models.router.call_model(), and
db helpers. It never imports a provider SDK directly (constraint 4/9.3)
and never does its own prompt string concatenation (Section 9).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import streamlit as st

from db import transaction
from models.registry import DEFAULT_MODEL_ID, list_models
from models.router import call_model
from prompting.assemble import build_prompt
from retrieval.hybrid_search import hybrid_search
from ui.cards import source_chips
from ui.theme import page_header


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_tasks(workspace_id: str) -> list[dict]:
    from db import get_connection

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
    from db import get_connection

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM workspaces WHERE workspace_id = ?", (workspace_id,)
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def _load_history(workspace_id: str, user_id: str) -> list[dict]:
    from db import get_connection

    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM chat_messages
            WHERE workspace_id = ? AND user_id = ?
            ORDER BY created_at
            """,
            (workspace_id, user_id),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _save_message(
    workspace_id: str,
    user_id: str,
    role: str,
    content: str,
    cited_sources: list[dict] | None = None,
    retrieved_chunk_ids: list[str] | None = None,
    task_id: str | None = None,
    model_id: str | None = None,
) -> None:
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO chat_messages
                (message_id, workspace_id, user_id, role, content,
                 cited_sources, retrieved_chunk_ids, task_id, model_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                workspace_id,
                user_id,
                role,
                content,
                json.dumps(cited_sources) if cited_sources is not None else None,
                json.dumps(retrieved_chunk_ids) if retrieved_chunk_ids is not None else None,
                task_id,
                model_id,
                _now(),
            ),
        )


def _clear_pending_error() -> None:
    """Drop any stashed turn error. Cleared at the start of every new send,
    on any (workspace_id, user_id) guard mismatch while rendering, and when a
    retry succeeds (SPEC.md §7.1)."""
    st.session_state.pop("wa_pending_error", None)


def _run_turn(
    workspace_id: str,
    user_id: str,
    user_input: str,
    model_id: str,
    task: dict | None = None,
) -> bool:
    """
    Retrieval + prompt assembly + model call + assistant-message persistence.
    Deliberately free of Streamlit (SPEC.md §7.1) so the caller owns the
    spinner and this can run from the Retry path too. Raises on any failure —
    nothing is persisted for the assistant unless this returns normally.

    Returns True when the turn ran with degraded retrieval — semantic search
    was unavailable and the answer is grounded in lexical (keyword) results
    only (SPEC.md §7.3); the caller surfaces the visible note. Returns False
    when both lexical and semantic retrieval were available.
    """
    workspace = _load_workspace(workspace_id)

    retrieval_query = user_input if not task else f"{task['name']} {user_input}"
    chunks, degraded = hybrid_search(retrieval_query, workspace_id, top_k=5)

    prompt = build_prompt(
        workspace_instructions=workspace.get("instructions", ""),
        retrieved_chunks=chunks,
        user_input=user_input,
        task_prompt=task["prompt"] if task else None,
        model_id=model_id,
    )

    answer_text = call_model(prompt, model_id=model_id)

    cited_sources = [
        {
            "source_id": c["source_id"],
            "display_name": c["display_name"],
            "section_title": c.get("section_title"),
        }
        for c in chunks
    ]
    retrieved_chunk_ids = [c["chunk_id"] for c in chunks]

    _save_message(
        workspace_id, user_id, "assistant", answer_text,
        cited_sources=cited_sources,
        retrieved_chunk_ids=retrieved_chunk_ids,
        task_id=task["task_id"] if task else None,
        model_id=model_id,
    )
    return degraded


def _stash_error(workspace_id: str, user_id: str, user_input: str,
                 model_id: str, task: dict | None, exc: Exception) -> None:
    st.session_state["wa_pending_error"] = {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "user_input": user_input,
        "model_id": model_id,
        "task": task,
        "error": str(exc),
    }


def _answer(
    workspace_id: str,
    user_id: str,
    user_input: str,
    model_id: str,
    task: dict | None = None,
) -> None:
    """
    Shared path for both free-form questions and task invocation
    (spec Section 9.1 — same assembly order, task adds a stored prompt).

    Error handling per SPEC.md §7.1:
      1. The user's message is persisted FIRST, in its own short transaction,
         before retrieval or the model call, so it survives any downstream
         failure.
      2. Retrieval + prompt assembly + model call are wrapped in try/except.
      3. On failure the error is stashed in session state (wa_pending_error)
         and rendered as an inline assistant bubble with a Retry control after
         the rerun — it never reaches Streamlit's error screen, and no
         assistant message is persisted.
      4. A successful turn that had to degrade to lexical-only retrieval (§7.3)
         sets wa_semantic_degraded so the chat view shows a visible note.
    """
    _clear_pending_error()
    st.session_state.pop("wa_semantic_degraded", None)
    _save_message(
        workspace_id, user_id, "user", user_input,
        task_id=task["task_id"] if task else None,
    )

    try:
        with st.spinner("Thinking..."):
            degraded = _run_turn(workspace_id, user_id, user_input, model_id, task=task)
    except Exception as exc:  # noqa: BLE001 - see §7.1
        _stash_error(workspace_id, user_id, user_input, model_id, task, exc)
        return
    if degraded:
        st.session_state["wa_semantic_degraded"] = True


def _retry() -> None:
    """Re-run the failed turn from the already-persisted user message.
    Never re-persists the user message (SPEC.md §7.1 / A13)."""
    payload = st.session_state.get("wa_pending_error")
    if not payload:
        return
    _clear_pending_error()
    st.session_state.pop("wa_semantic_degraded", None)
    try:
        with st.spinner("Thinking..."):
            degraded = _run_turn(
                payload["workspace_id"],
                payload["user_id"],
                payload["user_input"],
                payload["model_id"],
                task=payload.get("task"),
            )
    except Exception as exc:  # noqa: BLE001
        _stash_error(
            payload["workspace_id"], payload["user_id"],
            payload["user_input"], payload["model_id"],
            payload.get("task"), exc,
        )
        st.rerun()
        return
    if degraded:
        st.session_state["wa_semantic_degraded"] = True
    st.rerun()


def _render_pending_error(workspace_id: str, user_id: str) -> None:
    """Render the stashed turn error as an inline assistant bubble with a
    Retry control. Clears the stash if it belongs to a different user or
    Workspace (a stale error from another context must not show here)."""
    payload = st.session_state.get("wa_pending_error")
    if not payload:
        return
    if payload.get("workspace_id") != workspace_id or payload.get("user_id") != user_id:
        _clear_pending_error()
        return
    with st.chat_message("assistant"):
        st.error(
            "Something went wrong while answering. Your question was saved and "
            "is shown above — you can retry below."
        )
        with st.expander("Details (exception text)"):
            st.code(payload.get("error", "Unknown error"))
        if st.button("Retry", key="wa_retry_button"):
            _retry()


def _render_model_picker(workspace_id: str) -> str | None:
    """
    SPEC §14.3. list_models() already omits models whose .env slug is blank.
    Returns None when no model is configured (caller shows the no-model
    message); otherwise falls back from DEFAULT_MODEL_ID to the first
    configured model when the default's slug is unset (never crashes).
    """
    models = list_models()
    if not models:
        return None
    model_labels = {m.model_id: m.display_name for m in models}
    try:
        default_index = [m.model_id for m in models].index(DEFAULT_MODEL_ID)
    except ValueError:
        default_index = 0

    col_picker, col_note = st.columns([2, 3], vertical_alignment="center")
    with col_picker:
        selected_model_id = st.selectbox(
            "Model",
            options=[m.model_id for m in models],
            format_func=lambda mid: model_labels[mid],
            index=default_index,
            key=f"model_picker_{workspace_id}",
        )
    spec = next(m for m in models if m.model_id == selected_model_id)
    with col_note:
        st.markdown(
            f'<div style="opacity:0.6; font-size:0.82rem;">{spec.notes}</div>',
            unsafe_allow_html=True,
        )
    return selected_model_id


def _render_task_row(workspace_id: str, tasks: list[dict]) -> dict | None:
    st.markdown('<div class="wa-eyebrow">Predefined tasks</div>', unsafe_allow_html=True)

    if not tasks:
        st.caption("The Workspace owner hasn't configured any tasks yet.")
        return None

    selected_task_id = st.session_state.get(f"selected_task_{workspace_id}")
    n = len(tasks) + (1 if selected_task_id else 0)
    cols = st.columns(n)

    for i, task in enumerate(tasks):
        is_active = task["task_id"] == selected_task_id
        with cols[i]:
            if st.button(
                task["name"],
                key=f"task_btn_{task['task_id']}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state[f"selected_task_{workspace_id}"] = (
                    None if is_active else task["task_id"]
                )
                st.rerun()

    if selected_task_id:
        with cols[-1]:
            if st.button("Clear", key=f"clear_task_{workspace_id}", use_container_width=True):
                st.session_state[f"selected_task_{workspace_id}"] = None
                st.rerun()

    return next((t for t in tasks if t["task_id"] == selected_task_id), None)


def render_chat_view(workspace_id: str, user_id: str) -> None:
    workspace = _load_workspace(workspace_id)

    page_header(
        workspace.get("name", workspace_id),
        "Ask anything about the knowledge available in this Workspace.",
    )

    selected_model_id = _render_model_picker(workspace_id)
    if selected_model_id is None:
        # SPEC §14.3: no model configured in .env. App stays up; Manage and
        # ingestion continue to work (A20). The chat input stays visible but
        # any send fails gracefully via the §7.1 handler.
        st.warning(
            "No AI model is configured. Copy `.env.example` to `.env` and set "
            "`OPENAI_BASE_URL`, `OPENAI_API_KEY`, and at least one "
            "`OPENAI_MODEL_*` slug, then restart the app."
        )
    st.divider()

    # --- History ------------------------------------------------------------
    history = _load_history(workspace_id, user_id)
    if not history:
        st.markdown(
            '<div class="wa-empty">No messages yet — ask a question below, '
            'or pick a predefined task to get started.</div>',
            unsafe_allow_html=True,
        )
    for msg in history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if msg["role"] == "assistant" and msg.get("cited_sources"):
                source_chips(json.loads(msg["cited_sources"]))

    # --- Pending turn error (SPEC.md §7.1) rendered as the latest bubble ----
    _render_pending_error(workspace_id, user_id)

    # --- Semantic-retrieval degrade note (SPEC.md §7.3 / A15) ---------------
    if st.session_state.get("wa_semantic_degraded"):
        st.warning(
            "Semantic retrieval is unavailable in this session — the answer "
            "below is based on lexical (keyword) search only, so results may "
            "be less complete."
        )

    # --- Predefined tasks (constraint 7: no live "/" autocomplete) ----------
    tasks = _load_tasks(workspace_id)
    active_task = _render_task_row(workspace_id, tasks)

    if active_task:
        with st.container(border=True):
            st.markdown(
                f'<span class="wa-task-label">{active_task["name"]}</span>'
                f' <span style="opacity:0.65;">— {active_task["description"]}</span>',
                unsafe_allow_html=True,
            )
            with st.form(key=f"task_form_{active_task['task_id']}"):
                task_input = st.text_area(active_task["input_label"], height=120)
                submitted = st.form_submit_button("Run task", type="primary")
            if submitted and task_input.strip():
                _answer(workspace_id, user_id, task_input, selected_model_id, task=active_task)
                st.session_state[f"selected_task_{workspace_id}"] = None
                st.rerun()

    # --- Free-form chat input -------------------------------------------------
    user_question = st.chat_input("Type your question...")
    if user_question:
        _answer(workspace_id, user_id, user_question, selected_model_id, task=None)
        st.rerun()

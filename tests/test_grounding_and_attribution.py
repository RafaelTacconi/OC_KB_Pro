"""
test_grounding_and_attribution.py — SPEC.md §5.2.4 (A17) and §7.5.

AppTest end-to-end checks, run AS A MEMBER specifically — the failure mode for
§5.2.4 is the Member path rendering nothing while the Owner path looks right.

  A17  — a Workspace with zero indexed Sources shows a visible warning to
         Members, not only to the Owner.
  §5.2.4 — >0 indexed Sources shows a neutral caption to all users; failed
         Sources -> Owners only.
  §7.5  — assistant messages with model_id render the model's display name;
         an unknown model_id falls back to the raw id instead of hiding
         provenance (Step 6 item 1).
"""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

REPO_ROOT = Path(__file__).resolve().parents[1]

_NOW = "2026-09-11T00:00:00+00:00"


def _init_db(tmp_path):
    """Bootstrap the DB so tables exist before seeding."""
    import db as db_module

    db_module.init_db()
    db_module.migrate_db()
    # seed users + workspace so FKs hold
    from config import bootstrap

    bootstrap()


def _seed_source(db_path: Path, status: str) -> str:
    """Insert one source row; return its source_id."""
    source_id = uuid.uuid4().hex
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO sources
                (source_id, workspace_id, source_type, display_name, origin_ref,
                 status, error_message, indexed_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (source_id, "aml-workspace", "pdf", f"{status}.pdf",
             f"data/aml-workspace/sources/{source_id}.pdf", status,
             "boom" if status == "failed" else None,
             _NOW if status == "indexed" else None, _NOW),
        )
        conn.commit()
    finally:
        conn.close()
    return source_id


def _switch_to_member(at: AppTest) -> None:
    at.sidebar.selectbox[0].set_value("u_member1").run()


def _seed_message(db_path: Path, role: str, model_id: str | None) -> None:
    """Insert a message directly (no model call needed)."""
    conn = sqlite3.connect(db_path)
    try:
        chat_id = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO chats (chat_id, workspace_id, user_id, title, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (chat_id, "aml-workspace", "u_member1", "seed", _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO chat_messages (message_id, chat_id, workspace_id, user_id, role, "
            "content, cited_sources, retrieved_chunk_ids, task_id, model_id, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (uuid.uuid4().hex, chat_id, "aml-workspace", "u_member1", role,
             "answer text" if role == "assistant" else "question",
             None, None, None, model_id, _NOW),
        )
        conn.commit()
    finally:
        conn.close()


def test_a17_member_sees_warning_when_zero_indexed(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception

    # Switch to a member on a fresh (empty) workspace.
    _switch_to_member(at)
    assert not at.exception
    # The grounded-knowledge gap is shown to everyone as a GREY note
    # (UI review: grey not yellow) rendered via st.markdown/pill, not
    # st.warning. A17 requires the Member to SEE it.
    assert any(
        "No indexed knowledge yet" in (m.value or "") for m in at.markdown
    )


def test_grounding_caption_shows_count_to_member_when_indexed(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _init_db(tmp_path)
    _seed_source(tmp_path / "data" / "workspace_app.db", "indexed")
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    _switch_to_member(at)
    assert not at.exception
    assert any("1 source indexed." in c.value for c in at.caption)
    # UI review item 4: the MEMBER sees WHICH file is indexed, not just a count.
    assert any("Indexed files: indexed.pdf" in c.value for c in at.caption)
    # And the no-knowledge gap note is gone (it is html-markdown now).
    assert not any("No indexed knowledge yet" in (m.value or "") for m in at.markdown)


def test_failed_sources_note_is_owner_only(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _init_db(tmp_path)
    db_path = tmp_path / "data" / "workspace_app.db"
    _seed_source(db_path, "failed")
    _seed_source(db_path, "indexed")

    # Owner sees the failed note.
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    owner_sees = any(
        "failed to index" in c.value for c in at.caption
    )
    assert owner_sees

    # Member does NOT see the failed detail.
    _switch_to_member(at)
    assert not at.exception
    member_sees = any("failed to index" in c.value for c in at.caption)
    assert not member_sees
    # But the member still sees the count caption (indexed = 1).
    assert any("1 source indexed." in c.value for c in at.caption)


def test_model_attribution_renders_display_name(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _init_db(tmp_path)
    _seed_message(tmp_path / "data" / "workspace_app.db", "assistant", "internal-standard")
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    # Need to be in the chat view with the member's chat selected. Member has
    # one chat (seeded); default to it.
    _switch_to_member(at)
    assert not at.exception
    assert any("Model: Standard" in c.value for c in at.caption)


def test_model_attribution_falls_back_to_raw_id_for_unknown(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _init_db(tmp_path)
    _seed_message(tmp_path / "data" / "workspace_app.db", "assistant", "model-gone")
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    _switch_to_member(at)
    assert not at.exception
    # Unknown id falls back to the RAW model_id (Step 6 item 1).
    assert any("Model: model-gone" in c.value for c in at.caption)
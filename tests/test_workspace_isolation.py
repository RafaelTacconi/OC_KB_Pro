"""
test_workspace_isolation.py — SPEC §10 acceptance criterion A2.

"Uploading a Source to Workspace A never causes it to be retrieved when
chatting in Workspace B. Verify at the retrieval layer, not only in the UI."

The lexical and semantic paths filter on workspace_id independently
(SPEC §3.1), so this test checks EACH separately:

  - lexical_search: `WHERE chunks_fts MATCH ? AND chunks.workspace_id = ?`
  - semantic_search: `WHERE chunks.workspace_id = ? AND chunks.embedding IS NOT NULL`

The embedding model is stubbed (deterministic zero-vector) so the test needs
no network/HF download — we only care about workspace scoping, not ranking.
"""

from __future__ import annotations

import numpy as np
import pytest

import db as db_module
from retrieval import hybrid_search as hs

EMB_DIM = 384
_FAKE_NOW = "2026-09-11T00:00:00+00:00"


class _FakeModel:
    """Returns a fixed vector so cosine runs without loading the real model."""

    def encode(self, text: str):
        return np.zeros(EMB_DIM, dtype="float32")


@pytest.fixture()
def two_workspace_db(tmp_path, monkeypatch):
    """Two Workspaces (ws-a AML, ws-b HR), one Source + two chunks each, both
    FTS-synced and embedded with fake vectors. Uses the DEFAULT DB path so
    the retrieval functions (get_connection() default) hit the same file."""
    monkeypatch.setattr(hs, "_get_embedding_model", lambda: _FakeModel())
    monkeypatch.chdir(tmp_path)  # default DB_PATH -> tmp_path/data/workspace_app.db
    db_module.init_db()
    db_module.migrate_db()
    db_path = db_module.DB_PATH

    conn = db_module.get_connection()
    try:
        for ws in ("ws-a", "ws-b"):
            conn.execute(
                "INSERT INTO workspaces (workspace_id, name, owner_user_id, "
                "instructions, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                (ws, ws, "u_owner", "", _FAKE_NOW, _FAKE_NOW),
            )
        conn.execute("INSERT INTO users VALUES (?,?,?)", ("u_owner", "Owner", "owner"))
        conn.execute(
            "INSERT INTO workspace_members VALUES (?,?)", ("ws-a", "u_owner")
        )
        conn.execute(
            "INSERT INTO workspace_members VALUES (?,?)", ("ws-b", "u_owner")
        )

        sources = {
            "ws-a": ("src-a", "AML_Policy.pdf"),
            "ws-b": ("src-b", "HR_Policy.pdf"),
        }
        for ws, (sid, name) in sources.items():
            conn.execute(
                "INSERT INTO sources (source_id, workspace_id, source_type, "
                "display_name, origin_ref, status, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (sid, ws, "pdf", name, f"data/{ws}/sources/{sid}.pdf", "indexed", _FAKE_NOW),
            )

        chunk_specs = [
            # ws-a chunks — AML language
            ("c-a1", "src-a", "ws-a", "AML escalation window is 12 hours."),
            ("c-a2", "src-a", "ws-a", "AML approval authority sits with the MLRO."),
            # ws-b chunks — HR language, deliberately shares some words
            ("c-b1", "src-b", "ws-b", "HR leave escalation goes to the people team."),
            ("c-b2", "src-b", "ws-b", "HR approval for annual leave."),
        ]
        for cid, sid, ws, text in chunk_specs:
            emb = np.zeros(EMB_DIM, dtype="float32").tobytes()
            conn.execute(
                "INSERT INTO chunks (chunk_id, source_id, workspace_id, section_title, "
                "text, embedding_text, embedding, token_count, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (cid, sid, ws, None, text, text, emb, 10, _FAKE_NOW),
            )
        # FTS sync for both workspaces.
        for cid, sid, ws, text in chunk_specs:
            row = conn.execute(
                "SELECT rowid FROM chunks WHERE chunk_id = ?", (cid,)
            ).fetchone()
            conn.execute(
                "INSERT INTO chunks_fts (rowid, text, section_title) VALUES (?,?,NULL)",
                (row["rowid"], text),
            )
        conn.commit()
    finally:
        conn.close()

    def ws_of_chunk(chunk_id: str) -> str:
        mapping = {c: w for c, _, w, _ in chunk_specs}
        return mapping[chunk_id]

    return db_path, ws_of_chunk


def _assert_only_from_workspace(chunks: list[dict], ws_of_chunk, expected_ws: str) -> None:
    assert chunks, "expected at least one retrieved chunk"
    for c in chunks:
        assert ws_of_chunk(c["chunk_id"]) == expected_ws, (
            f"chunk {c['chunk_id']} leaked across Workspace boundary"
        )


def test_lexical_search_never_crosses_workspace(two_workspace_db):
    db_path, ws_of_chunk = two_workspace_db
    # Query about 'escalation' — present in BOTH ws-a (c-a1) and ws-b (c-b1),
    # so the FTS filter must keep ws-b's chunk out of a ws-a search.
    results = hs.lexical_search("escalation", "ws-a", top_k=10)
    _assert_only_from_workspace(results, ws_of_chunk, "ws-a")
    assert any(c["chunk_id"] == "c-a1" for c in results)


def test_semantic_search_never_crosses_workspace(two_workspace_db):
    db_path, ws_of_chunk = two_workspace_db
    results = hs.semantic_search("anything", "ws-a", top_k=10)
    _assert_only_from_workspace(results, ws_of_chunk, "ws-a")


def test_hybrid_search_never_crosses_workspace(two_workspace_db):
    db_path, ws_of_chunk = two_workspace_db
    chunks, degraded = hs.hybrid_search("escalation approval", "ws-a", top_k=10)
    assert degraded is False
    _assert_only_from_workspace(chunks, ws_of_chunk, "ws-a")
    assert any(c["chunk_id"] in ("c-a1", "c-a2") for c in chunks)
"""
test_activity_log.py — Tier 1 logging (SPEC §19 / A55).

No live model, no network. Uses temp DB files only.
"""

from __future__ import annotations

import pytest

from activity_log import get_log_connection, init_log_db, log_turn, refusal_rate


def test_log_turn_writes_exact_tier1_fields_without_text(tmp_path):
    db = tmp_path / "logs.db"
    init_log_db(db)
    log_turn(
        "ui",
        workspace_id="ws1",
        requester="u_owner",
        chat_id="chat1",
        question_chars=42,
        chunks_retrieved=3,
        lexical_degrade=True,
        model_slug="std-real",
        retrieval_ms=12.5,
        total_ms=99.0,
        outcome="answered",
        db_path=db,
    )
    conn = get_log_connection(db)
    try:
        rows = [dict(r) for r in conn.execute("SELECT * FROM tier1_turn_log")]
    finally:
        conn.close()

    assert len(rows) == 1
    r = rows[0]
    assert r["source"] == "ui"
    assert r["workspace_id"] == "ws1"
    assert r["requester"] == "u_owner"
    assert r["chat_id"] == "chat1"
    assert r["question_chars"] == 42
    assert r["chunks_retrieved"] == 3
    assert r["lexical_degrade"] == 1
    assert r["model_slug"] == "std-real"
    assert r["outcome"] == "answered"
    assert r["error_type"] is None
    # Tier 1 must hold no question/answer TEXT: no such column exists at all.
    assert not any("text" == c.lower() or "question_text" in c.lower() or "answer" in c.lower() for c in r)


def test_log_turn_never_raises(tmp_path):
    # Passing a directory as the DB path makes sqlite fail; log_turn must swallow it.
    log_turn("ui", db_path=tmp_path)


def test_refusal_rate_computable_from_tier1(tmp_path):
    db = tmp_path / "logs.db"
    init_log_db(db)
    log_turn("api", workspace_id="w", outcome="refused", db_path=db)
    log_turn("api", workspace_id="w", outcome="answered", db_path=db)
    log_turn("ui", workspace_id="w", outcome="error", error_type="RuntimeError", db_path=db)

    rr = refusal_rate("w", db_path=db)
    assert rr["refused"] == 1
    assert rr["answered"] == 1
    assert rr["error"] == 1
    assert rr["total"] == 3
    assert rr["refusal_rate"] == pytest.approx(1 / 3)

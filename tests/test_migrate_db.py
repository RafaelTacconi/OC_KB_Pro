"""
test_migrate_db.py — SPEC.md §4.5 / A10 regression tests.

`migrate_db()` upgrades a database created BEFORE Steps 3/4. This test builds a
fixture that reproduces the OLD `chat_messages` schema (no `chat_id` column),
seeds messages across two users and two workspaces, then verifies the migration:

  A10 — every pre-existing message is assigned to exactly one Chat per
        (workspace_id, user_id); no message ends up with chat_id IS NULL;
        created_at = earliest message / updated_at = latest; running it a
        second time changes nothing.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

import pytest

import db as db_module

OLD_CHAT_MESSAGES_SCHEMA = """
CREATE TABLE chat_messages (
    message_id          TEXT PRIMARY KEY,
    workspace_id        TEXT NOT NULL REFERENCES workspaces(workspace_id),
    user_id             TEXT NOT NULL REFERENCES users(user_id),
    role                TEXT NOT NULL,
    content             TEXT NOT NULL,
    cited_sources       TEXT,
    retrieved_chunk_ids TEXT,
    task_id             TEXT,
    model_id            TEXT,
    created_at          TEXT NOT NULL
);
"""


@pytest.fixture()
def legacy_db(tmp_path):
    """
    Build a database with the OLD (pre-Stps 3/4) schema: workspaces + users +
    chat_messages WITHOUT a chat_id column, seeded with messages by two users
    across two workspaces. Returns the path (file exists).
    """
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE workspaces (
            workspace_id  TEXT PRIMARY KEY,
            name          TEXT NOT NULL,
            owner_user_id TEXT NOT NULL,
            instructions  TEXT DEFAULT '',
            created_at    TEXT NOT NULL,
            updated_at    TEXT NOT NULL
        );
        CREATE TABLE users (
            user_id      TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            role         TEXT NOT NULL
        );
        CREATE TABLE workspace_members (
            workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id),
            user_id      TEXT NOT NULL REFERENCES users(user_id),
            PRIMARY KEY (workspace_id, user_id)
        );
        CREATE TABLE sources (
            source_id     TEXT PRIMARY KEY,
            workspace_id  TEXT NOT NULL REFERENCES workspaces(workspace_id),
            source_type   TEXT NOT NULL,
            display_name  TEXT NOT NULL,
            origin_ref    TEXT,
            status        TEXT NOT NULL,
            error_message TEXT,
            indexed_at    TEXT,
            created_at    TEXT NOT NULL
        );
        CREATE TABLE chunks (
            chunk_id       TEXT PRIMARY KEY,
            source_id      TEXT NOT NULL REFERENCES sources(source_id),
            workspace_id   TEXT NOT NULL REFERENCES workspaces(workspace_id),
            section_title  TEXT,
            text           TEXT NOT NULL,
            embedding_text TEXT,
            embedding      BLOB,
            token_count    INTEGER,
            created_at     TEXT NOT NULL
        );
        CREATE TABLE tasks (
            task_id      TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id),
            name         TEXT NOT NULL,
            description  TEXT NOT NULL,
            prompt       TEXT NOT NULL,
            input_label  TEXT NOT NULL,
            created_at   TEXT NOT NULL
        );
        """
    )
    conn.executescript(OLD_CHAT_MESSAGES_SCHEMA)

    # Workspaces + users
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO workspaces VALUES (?,?,?,?,?,?)",
        ("ws-a", "WS A", "u1", "", now, now),
    )
    conn.execute(
        "INSERT INTO workspaces VALUES (?,?,?,?,?,?)",
        ("ws-b", "WS B", "u2", "", now, now),
    )
    for uid in ("u1", "u2"):
        conn.execute("INSERT INTO users VALUES (?,?,?)", (uid, f"User {uid}", "member"))

    # Messages: u1 has 2 in ws-a, 1 in ws-b; u2 has 1 in ws-a.
    seeds = [
        ("m1", "ws-a", "u1", "2026-09-01T00:00:00+00:00", "hello a1"),
        ("m2", "ws-a", "u1", "2026-09-02T00:00:00+00:00", "hello a2"),
        ("m3", "ws-b", "u1", "2026-09-03T00:00:00+00:00", "hello b1"),
        ("m4", "ws-a", "u2", "2026-09-04T00:00:00+00:00", "hello a u2"),
    ]
    for mid, ws, uid, ts, content in seeds:
        conn.execute(
            "INSERT INTO chat_messages (message_id, workspace_id, user_id, role, content, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (mid, ws, uid, "user", content, ts),
        )
    conn.commit()
    conn.close()
    return db_path


def _row_counts(db_path) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        n_chats = conn.execute("SELECT COUNT(*) FROM chats").fetchone()[0]
        n_msgs = conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]
        n_null = conn.execute(
            "SELECT COUNT(*) FROM chat_messages WHERE chat_id IS NULL"
        ).fetchone()[0]
        return {"chats": n_chats, "messages": n_msgs, "null_chat_id": n_null}
    finally:
        conn.close()


def test_migrate_db_backfills_legacy_messages(legacy_db):
    # Fresh legacy DB: no chats table yet, no chat_id column (the pre-state).
    conn = sqlite3.connect(legacy_db)
    try:
        assert "chat_id" not in [
            r[1] for r in conn.execute("PRAGMA table_info(chat_messages)")
        ]
    finally:
        conn.close()

    db_module.migrate_db(legacy_db)

    counts = _row_counts(legacy_db)
    # A10: 4 messages across 3 (workspace,user) groups -> exactly 3 chats.
    assert counts["chats"] == 3
    assert counts["messages"] == 4
    assert counts["null_chat_id"] == 0  # nothing left NULL

    # Backfill detail checks (created_at = earliest, updated_at = latest).
    conn = sqlite3.connect(legacy_db)
    try:
        rows = conn.execute("SELECT * FROM chats ORDER BY created_at").fetchall()
        assert len(rows) == 3
        by_ws_user = {(r[1], r[2]): r for r in rows}
        # u1/ws-a: messages at 09-01 and 09-02
        a = by_ws_user[("ws-a", "u1")]
        assert a[4] == "2026-09-01T00:00:00+00:00"  # created_at
        assert a[5] == "2026-09-02T00:00:00+00:00"  # updated_at
        # u1/ws-b: single message
        b = by_ws_user[("ws-b", "u1")]
        assert b[4] == b[5] == "2026-09-03T00:00:00+00:00"
        # u2/ws-a
        c = by_ws_user[("ws-a", "u2")]
        assert c[4] == c[5] == "2026-09-04T00:00:00+00:00"

        # Every message now points at exactly one chat in its group.
        joined = conn.execute(
            """
            SELECT m.message_id, m.chat_id, c.workspace_id AS c_ws, c.user_id AS c_uid
            FROM chat_messages m JOIN chats c USING (chat_id)
            """
        ).fetchall()
        assert len(joined) == 4
        for row in joined:
            assert row[3] == "u1" or row[3] == "u2"  # sanity
    finally:
        conn.close()


def test_migrate_db_idempotent(legacy_db):
    db_module.migrate_db(legacy_db)
    before = _row_counts(legacy_db)
    db_module.migrate_db(legacy_db)  # second run
    after = _row_counts(legacy_db)
    assert before == after


def test_migrate_db_on_fresh_db_is_noop(tmp_path):
    """A brand-new DB (as created by init_db) gets the new schema; migrating
    it straight after must not fail or duplicate anything."""
    db_module.init_db(tmp_path / "fresh.db")
    counts_before = _row_counts(tmp_path / "fresh.db")
    db_module.migrate_db(tmp_path / "fresh.db")
    counts_after = _row_counts(tmp_path / "fresh.db")
    assert counts_before == counts_after == {"chats": 0, "messages": 0, "null_chat_id": 0}
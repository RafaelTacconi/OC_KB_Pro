"""
db.py — SQLite connection management and schema.

Per spec Section 6.1 / constraint 9 (Section 5): WAL mode + busy_timeout is
mandatory from the very first connection, not an optimization to add later.
SQLite's default rollback-journal mode blocks all readers during any write;
WAL lets readers proceed concurrently but still allows only one writer at a
time. Without a busy_timeout, concurrent Streamlit reruns from different
test users will intermittently raise "database is locked" — exactly during
the PoC's own user-testing phase (acceptance criterion #10).

Keep every transaction short. Never hold a connection open across a network
call (call_model) or a slow parse (ingestion) — do the DB work, commit,
close/return, then do the slow external work.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path("data/workspace_app.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (
    workspace_id    TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    owner_user_id   TEXT NOT NULL,
    instructions    TEXT DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id         TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    role            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspace_members (
    workspace_id    TEXT NOT NULL REFERENCES workspaces(workspace_id),
    user_id         TEXT NOT NULL REFERENCES users(user_id),
    PRIMARY KEY (workspace_id, user_id)
);

-- source_type = 'confluence' is a reserved, not-yet-used value (spec 4a).
-- Do not build a UI path that sets it in this PoC.
CREATE TABLE IF NOT EXISTS sources (
    source_id       TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL REFERENCES workspaces(workspace_id),
    source_type     TEXT NOT NULL,
    display_name    TEXT NOT NULL,
    origin_ref      TEXT,
    status          TEXT NOT NULL,
    error_message   TEXT,
    indexed_at      TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id        TEXT PRIMARY KEY,
    source_id       TEXT NOT NULL REFERENCES sources(source_id),
    workspace_id    TEXT NOT NULL REFERENCES workspaces(workspace_id),
    section_title   TEXT,
    text            TEXT NOT NULL,
    embedding_text  TEXT,
    embedding       BLOB,
    token_count     INTEGER,
    created_at      TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    section_title,
    content='chunks',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id         TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL REFERENCES workspaces(workspace_id),
    name            TEXT NOT NULL,
    description     TEXT NOT NULL,
    prompt          TEXT NOT NULL,
    input_label     TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    message_id          TEXT PRIMARY KEY,
    workspace_id        TEXT NOT NULL REFERENCES workspaces(workspace_id),
    user_id             TEXT NOT NULL REFERENCES users(user_id),
    role                TEXT NOT NULL,
    content             TEXT NOT NULL,
    cited_sources       TEXT,
    retrieved_chunk_ids TEXT,
    task_id             TEXT,
    model_id            TEXT,   -- which AI model produced this message (assistant rows only)
    created_at          TEXT NOT NULL
);
"""


def get_connection(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    """
    Open a connection with WAL mode + busy_timeout applied. Call this for
    every connection opened anywhere in the app — never sqlite3.connect()
    directly outside this function.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10)  # driver-level retry window
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 8000;")  # 8s in ms, SQLite-level wait
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path = DB_PATH) -> None:
    """Create all tables/indexes if they don't already exist. Idempotent."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def transaction(db_path: str | Path = DB_PATH):
    """
    Short-lived transaction helper. Usage:
        with transaction() as conn:
            conn.execute(...)
    Commits on clean exit, rolls back on exception, always closes.
    Keep the `with` block free of network calls or slow parsing (Section 6.1).
    """
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

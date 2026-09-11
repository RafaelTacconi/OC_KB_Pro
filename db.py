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
import uuid
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
    image_count     INTEGER,        -- embedded images during parse (SPEC §15.1)
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

-- A Chat is a named conversation thread: one (Workspace, user) pair owns many
-- Chats; Messages belong to exactly one Chat (SPEC §4.2, §6).
CREATE TABLE IF NOT EXISTS chats (
    chat_id       TEXT PRIMARY KEY,
    workspace_id  TEXT NOT NULL REFERENCES workspaces(workspace_id),
    user_id       TEXT NOT NULL REFERENCES users(user_id),
    title         TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    message_id          TEXT PRIMARY KEY,
    chat_id             TEXT REFERENCES chats(chat_id),
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

# Indexes for the multi-Workspace / multi-Chat hot queries (SPEC §4.4).
# Kept separate from SCHEMA so migrate_db() can run them AFTER the legacy
# chat_messages table has been ALTERed to add chat_id — the index creation
# references chat_id, which a legacy table does not have yet.
INDEXES = """
CREATE INDEX IF NOT EXISTS idx_chunks_workspace   ON chunks(workspace_id);
CREATE INDEX IF NOT EXISTS idx_sources_workspace  ON sources(workspace_id);
CREATE INDEX IF NOT EXISTS idx_tasks_workspace    ON tasks(workspace_id);
CREATE INDEX IF NOT EXISTS idx_chats_ws_user      ON chats(workspace_id, user_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_messages_chat      ON chat_messages(chat_id, created_at);
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
        conn.executescript(INDEXES)
        conn.commit()
    finally:
        conn.close()


def migrate_db(db_path: str | Path = DB_PATH) -> None:
    """
    Idempotent migration for databases created before Steps 3/4 (SPEC §4.5).
    Safe on a fresh DB and safe to run repeatedly.

    Runs SCHEMA first (CREATE TABLE IF NOT EXISTS) so the `chats` table
    exists even if this is the first function to touch the DB — migrate_db()
    must be safe to call on a legacy DB alone, not only after init_db().
    The ALTER (add chat_id) runs BEFORE the indexes, because a legacy
    chat_messages table has no chat_id column for the index to reference.

    1. Add `chat_messages.chat_id` if absent (nullable at SQL level — legacy
       rows exist; app code enforces non-null, §4.3).
    2. Backfill: for each distinct (workspace_id, user_id) with NULL chat_id,
       create one `chats` row titled "Imported conversation" with
       created_at = earliest message timestamp, updated_at = latest.
    3. Add `sources.image_count` if absent (SPEC §15.1) — nullable; NULL means
       "not counted" for pre-existing/legacy rows.
    4. Create the indexing views (SPEC §4.4).
    """
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)  # ensure chats table (+ anything missing) exists
        # 1. chat_id column
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(chat_messages)")]
        if "chat_id" not in cols:
            conn.execute("ALTER TABLE chat_messages ADD COLUMN chat_id TEXT REFERENCES chats(chat_id)")

        # 3. sources.image_count (SPEC §15.1)
        source_cols = [r["name"] for r in conn.execute("PRAGMA table_info(sources)")]
        if "image_count" not in source_cols:
            conn.execute("ALTER TABLE sources ADD COLUMN image_count INTEGER")

        # 4. Indexes (AFTER the ALTERs — they reference chat_id).
        conn.executescript(INDEXES)

        # 2. Backfill — only rows still NULL (created before this migration).
        groups = conn.execute(
            """
            SELECT workspace_id, user_id,
                   MIN(created_at) AS first_at,
                   MAX(created_at) AS last_at
            FROM chat_messages
            WHERE chat_id IS NULL
            GROUP BY workspace_id, user_id
            """
        ).fetchall()
        for g in groups:
            chat_id = uuid.uuid4().hex
            conn.execute(
                """
                INSERT INTO chats (chat_id, workspace_id, user_id, title, created_at, updated_at)
                VALUES (?, ?, ?, 'Imported conversation', ?, ?)
                """,
                (chat_id, g["workspace_id"], g["user_id"], g["first_at"], g["last_at"]),
            )
            conn.execute(
                """
                UPDATE chat_messages SET chat_id = ?
                WHERE workspace_id = ? AND user_id = ? AND chat_id IS NULL
                """,
                (chat_id, g["workspace_id"], g["user_id"]),
            )

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

"""
activity_log.py — Tier 1 activity logging (SPEC.md §19).

Tier 1 is metadata ONLY: never question text, never answer text. Logs live in
their OWN SQLite database (SPEC §19.1) so a burst of logging can never block a
question through SQLite's single-writer lock on the knowledge-base database.
Tier 2 (question/answer text, per-Workspace, off by default) is NOT built.

Concurrency (SPEC §19.6): every connection sets WAL + busy_timeout, the same
policy as db.get_connection() (§6.1). The Streamlit process and the API process
each open short-lived connections; WAL gives one writer plus many readers and
busy_timeout absorbs the momentary lock between them. The MAIN database needs no
change: the API only reads it.

A logging failure must NEVER fail a question, so log_turn() swallows every
exception it raises. A question with no log row is acceptable; a failed question
because logging failed is not.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

LOG_DB_PATH = Path("data/logs.db")

# Exactly the SPEC §19.2 Tier 1 fields. `outcome` permits answered/refused/error
# (see §19.3 and §19.6: `refused` is populated for the observable empty-retrieval
# case; the wider refusal signal is OPEN-15 and is deliberately not decided).
SCHEMA = """
CREATE TABLE IF NOT EXISTS tier1_turn_log (
    log_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT    NOT NULL,
    workspace_id      TEXT,
    requester         TEXT,
    source            TEXT    NOT NULL,
    chat_id           TEXT,
    question_chars    INTEGER NOT NULL,
    chunks_retrieved  INTEGER NOT NULL,
    lexical_degrade   INTEGER NOT NULL,
    model_slug        TEXT,
    retrieval_ms      REAL,
    total_ms          REAL,
    outcome           TEXT    NOT NULL,
    error_type        TEXT
);
CREATE INDEX IF NOT EXISTS idx_tier1_ts        ON tier1_turn_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_tier1_ws_ts     ON tier1_turn_log(workspace_id, timestamp);
"""


def get_log_connection(db_path: str | Path = LOG_DB_PATH) -> sqlite3.Connection:
    """Open the log database with WAL + busy_timeout (SPEC §19.6). Kept
    independent of db.get_connection() so the two databases never share a
    connection or a lock."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 8000;")
    conn.row_factory = sqlite3.Row
    return conn


def init_log_db(db_path: str | Path = LOG_DB_PATH) -> None:
    """Create the Tier 1 table/indexes if absent. Idempotent."""
    conn = get_log_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


# Tracks which (absolute) log DB paths this process has already initialised, so
# log_turn() works even if the caller forgot init_log_db() — the API and the UI
# must both be able to log without a startup dance. Keyed by RESOLVED path so a
# test that chdirs to a fresh tmp dir still initialises the fresh file.
_initialized: set[str] = set()


def _ensure_log_db(db_path: str | Path) -> None:
    key = str(Path(db_path).resolve())
    if key not in _initialized:
        init_log_db(db_path)
        _initialized.add(key)


def log_turn(
    source: str,
    *,
    workspace_id: str | None = None,
    requester: str | None = None,
    chat_id: str | None = None,
    question_chars: int = 0,
    chunks_retrieved: int = 0,
    lexical_degrade: bool = False,
    model_slug: str | None = None,
    retrieval_ms: float | None = None,
    total_ms: float | None = None,
    outcome: str = "answered",
    error_type: str | None = None,
    db_path: str | Path = LOG_DB_PATH,
) -> None:
    """
    Write one Tier 1 row. `source` is "ui" or "api". `outcome` is one of
    answered / refused / error. This function NEVER raises — a logging failure
    must not fail the question (SPEC §19.6).
    """
    try:
        _ensure_log_db(db_path)
        conn = get_log_connection(db_path)
        try:
            conn.execute(
                """
                INSERT INTO tier1_turn_log
                    (timestamp, workspace_id, requester, source, chat_id,
                     question_chars, chunks_retrieved, lexical_degrade,
                     model_slug, retrieval_ms, total_ms, outcome, error_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    workspace_id,
                    requester,
                    source,
                    chat_id,
                    int(question_chars),
                    int(chunks_retrieved),
                    1 if lexical_degrade else 0,
                    model_slug,
                    retrieval_ms,
                    total_ms,
                    outcome,
                    error_type,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 - logging must never fail a question
        pass


def refusal_rate(
    workspace_id: str | None = None,
    db_path: str | Path = LOG_DB_PATH,
) -> dict:
    """
    The primary metric (SPEC §19.3), computable from Tier 1 alone: the fraction
    of turns whose `outcome` is `refused`. Optionally sliced to one Workspace.

    NOTE: `refused` is currently produced only by the API's empty-retrieval
    short-circuit (§20.5). The wider refusal — chunks retrieved but not answering
    — needs the signal OPEN-15 has not decided (SPEC §19.6). Returns a dict with
    the counts so the caller can compute any rate they want.
    """
    conn = get_log_connection(db_path)
    try:
        where = "WHERE workspace_id = ?" if workspace_id else ""
        params = (workspace_id,) if workspace_id else ()
        rows = conn.execute(
            f"SELECT outcome, COUNT(*) AS n FROM tier1_turn_log {where} GROUP BY outcome",
            params,
        ).fetchall()
        counts = {r["outcome"]: r["n"] for r in rows}
    finally:
        conn.close()
    total = sum(counts.values())
    refused = counts.get("refused", 0)
    return {
        "answered": counts.get("answered", 0),
        "refused": refused,
        "error": counts.get("error", 0),
        "total": total,
        "refusal_rate": (refused / total) if total else 0.0,
    }

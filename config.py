"""
config.py — fixed test-user list and seed helpers.

Per spec constraint 6 (Section 5): no real authentication for the PoC.
A hardcoded test-user list is correct and expected. Do not build login/SSO.

SPEC §14.2: load_dotenv() runs at import (app.py imports this early), so
`models/` lazy environment reads see `.env` values regardless of import order.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

from db import transaction

load_dotenv()  # no-op with no .env present — never a crash on startup (SPEC §14.2)

# Edit this list for your actual PoC test group.
TEST_USERS = [
    {"user_id": "u_owner", "display_name": "Alex (Owner)", "role": "owner"},
    {"user_id": "u_member1", "display_name": "Priya (Member)", "role": "member"},
    {"user_id": "u_member2", "display_name": "Sam (Member)", "role": "member"},
]

DEFAULT_WORKSPACE_ID = "aml-workspace"
DEFAULT_WORKSPACE_NAME = "AML Workspace"

# Two hardcoded example tasks to prove the "/" mechanism (spec: 2-3 tasks, Section 4.2).
SEED_TASKS = [
    {
        "name": "/summarize-policy",
        "description": "Produces a short summary of a policy document.",
        "prompt": (
            "You are summarizing a policy document for a busy team member. "
            "Produce a concise summary (5-8 bullet points) covering: scope, "
            "who it applies to, key obligations, and any explicit thresholds "
            "or deadlines mentioned. Use only the retrieved knowledge provided; "
            "cite the source for each bullet."
        ),
        "input_label": "Paste or name the policy you want summarized",
    },
    {
        "name": "/find-procedure",
        "description": "Finds the documented procedure for a described situation.",
        "prompt": (
            "The user will describe a situation. Find the documented procedure "
            "that applies, using only the retrieved knowledge provided. State "
            "the procedure step by step, with a citation. If no procedure in "
            "the knowledge base covers the situation, say so explicitly rather "
            "than improvising one."
        ),
        "input_label": "Describe the situation you need a procedure for",
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_users() -> None:
    with transaction() as conn:
        for user in TEST_USERS:
            conn.execute(
                """
                INSERT INTO users (user_id, display_name, role)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO NOTHING
                """,
                (user["user_id"], user["display_name"], user["role"]),
            )


def seed_default_workspace() -> None:
    with transaction() as conn:
        existing = conn.execute(
            "SELECT 1 FROM workspaces WHERE workspace_id = ?",
            (DEFAULT_WORKSPACE_ID,),
        ).fetchone()
        if existing:
            return

        owner_id = next(u["user_id"] for u in TEST_USERS if u["role"] == "owner")
        now = _now()
        conn.execute(
            """
            INSERT INTO workspaces
                (workspace_id, name, owner_user_id, instructions, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                DEFAULT_WORKSPACE_ID,
                DEFAULT_WORKSPACE_NAME,
                owner_id,
                "You are an assistant for this team. Only rely on information "
                "in this Workspace. If sources don't support an answer, say so. "
                "Always cite the source used.",
                now,
                now,
            ),
        )
        for user in TEST_USERS:
            conn.execute(
                """
                INSERT INTO workspace_members (workspace_id, user_id)
                VALUES (?, ?)
                ON CONFLICT DO NOTHING
                """,
                (DEFAULT_WORKSPACE_ID, user["user_id"]),
            )
        for task in SEED_TASKS:
            conn.execute(
                """
                INSERT INTO tasks
                    (task_id, workspace_id, name, description, prompt, input_label, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    DEFAULT_WORKSPACE_ID,
                    task["name"],
                    task["description"],
                    task["prompt"],
                    task["input_label"],
                    now,
                ),
            )


def bootstrap() -> None:
    """Call once at app startup — idempotent."""
    from db import init_db

    init_db()
    seed_users()
    seed_default_workspace()

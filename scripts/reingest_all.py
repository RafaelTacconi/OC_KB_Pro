"""
scripts/reingest_all.py — the one re-ingestion pass for the §22 bundle (SPEC §22.6).

TOOL, NOT A TEST. It is NOT under tests/, is NOT collected by pytest, and it
asserts nothing. The owner runs it ONCE, from his own terminal with the venv
active, AFTER he has made the hand-made dated copy of the database:

    Copy-Item data\\workspace_app.db "data\\workspace_app_YYYY-MM-DD.pre-reingest.db"
    python -m scripts.reingest_all

Per Workspace it:
  - reads the ORIGINAL SOURCE BYTES already stored under
    data/{workspace_id}/sources/ — the owner re-uploads nothing;
  - replaces each source's index (clear its chunks, then re-ingest) via
    ingestion.pipeline.reingest_source, so every chunk_id is regenerated;
  - prints the document count and the chunk count BEFORE and AFTER, so the owner
    can see at a glance that nothing vanished.

It DELETES NOTHING under data/ (AGENTS.md rule 7) — it only rewrites database
rows. It does not touch retrieval/, prompting/, or any retrieval setting.
"""

from __future__ import annotations

import sys
from pathlib import Path

from db import get_connection
from ingestion.pipeline import reingest_source

# SPEC §22.6 — all five Workspaces, re-ingested in one pass.
WORKSPACES = [
    "aml-workspace",
    "62ee0cd0d2324cd5ab5e20b70a8b27bc",
    "aa6dc06b19dd47e1a24d4855b951d24f",
    "524bf0ec5c5f4290a80438fd801455ce",
    "d93d5cd12269400e9298c535062afc65",
]

DATA_DIR = Path("data")


def _counts(workspace_id: str) -> tuple[int, int]:
    conn = get_connection()
    try:
        documents = conn.execute(
            "SELECT COUNT(*) FROM sources WHERE workspace_id = ?", (workspace_id,)
        ).fetchone()[0]
        chunks = conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE workspace_id = ?", (workspace_id,)
        ).fetchone()[0]
        return documents, chunks
    finally:
        conn.close()


def _sources(workspace_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT source_id, source_type FROM sources WHERE workspace_id = ? "
            "ORDER BY display_name",
            (workspace_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _stored_path(workspace_id: str, source: dict) -> Path:
    return DATA_DIR / workspace_id / "sources" / f"{source['source_id']}.{source['source_type']}"


def main(argv: list[str] | None = None) -> int:
    print("Re-ingestion pass for SPEC §22 (five Workspaces). Nothing under data/ is deleted.")
    for workspace_id in WORKSPACES:
        docs_before, chunks_before = _counts(workspace_id)
        print(
            f"\nWorkspace {workspace_id}: documents={docs_before} "
            f"chunks={chunks_before} (before)"
        )
        for source in _sources(workspace_id):
            path = _stored_path(workspace_id, source)
            if not path.exists():
                print(
                    f"  MISSING stored bytes for {source['source_id']} "
                    f"({source['source_type']}) — skipped"
                )
                continue
            print(f"  re-ingesting {source['source_id']} ({source['source_type']}) ...")
            reingest_source(str(path), source["source_type"], source["source_id"], workspace_id)
        docs_after, chunks_after = _counts(workspace_id)
        print(
            f"Workspace {workspace_id}: documents={docs_after} "
            f"chunks={chunks_after} (after)"
        )
    print("\nDone. Run the four acceptance checks by hand (SPEC §22.7).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

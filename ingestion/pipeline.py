"""
pipeline.py — the ingestion module's single public entry point.

Per spec Section 7.5 / constraint 3 (Section 5): `ingest_source()` is the
ONLY function Streamlit UI code (or any Workspace/chat logic) may call from
the ingestion package. Everything else here (parsers, chunking, embedding,
FTS sync) is a private implementation detail. This boundary is what makes
adding a future source type (e.g. 'confluence', per Section 4a) a matter of
adding one branch inside this function, not touching any caller.

Also per constraint 3: this module must not import Streamlit. Status/progress
is communicated purely through the `sources` table row (status, error_message),
which the UI polls/displays via st.status() — see ui/owner_view.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from db import get_connection, transaction
from ingestion.chunking import build_embedding_text, chunk_text
from ingestion.embedding import embed_batch
from ingestion.parsers import count_embedded_images, parse

SUPPORTED_SOURCE_TYPES = {"pdf", "docx", "xlsx"}  # 'confluence' reserved, not active (4a)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ingest_source(file_path: str, source_type: str, source_id: str, workspace_id: str) -> None:
    """
    Parses, chunks, embeds, and indexes a single source.

    Updates sources.status and sources.error_message as it progresses.
    Raises nothing to the caller — all failure states are written to the
    sources row (per spec: "do not fail silently" applies to the *user*,
    not to exceptions escaping this function; callers should still be able
    to trust this returns normally and check `status` afterward).
    """
    _set_status(source_id, "processing")

    try:
        if source_type not in SUPPORTED_SOURCE_TYPES:
            raise ValueError(
                f"source_type {source_type!r} is not supported in this build. "
                f"(Confluence is reserved for a future round — see spec Section 4a.)"
            )

        # SPEC §15.1: count embedded images so the Owner can be told their
        # content is not indexed. Count is a floor; never blocks ingestion.
        image_count = count_embedded_images(file_path, source_type)

        sections = parse(file_path, source_type)
        if not sections:
            raise ValueError("Parsing produced no extractable text from this file.")

        all_chunks: list[dict] = []
        for section in sections:
            all_chunks.extend(
                chunk_text(
                    section.text,
                    section_title=section.section_title,
                    page=section.page,
                )
            )

        if not all_chunks:
            raise ValueError("Chunking produced no chunks from the parsed content.")

        embedding_inputs = [build_embedding_text(c) for c in all_chunks]
        embedding_blobs = embed_batch(embedding_inputs)

        with transaction() as conn:
            for chunk, emb_text, emb_blob in zip(all_chunks, embedding_inputs, embedding_blobs):
                chunk_id = uuid.uuid4().hex
                conn.execute(
                    """
                    INSERT INTO chunks
                        (chunk_id, source_id, workspace_id, section_title, page,
                         text, embedding_text, embedding, token_count, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk_id,
                        source_id,
                        workspace_id,
                        chunk["section_title"],
                        chunk.get("page"),
                        chunk["text"],
                        emb_text,
                        emb_blob,
                        chunk["token_count"],
                        _now(),
                    ),
                )
            _sync_fts(conn, source_id)

            conn.execute(
                """
                UPDATE sources
                SET status = 'indexed', error_message = NULL, indexed_at = ?,
                    image_count = ?
                WHERE source_id = ?
                """,
                (_now(), image_count, source_id),
            )

    except Exception as exc:  # noqa: BLE001 - intentionally broad; see docstring
        _set_status(source_id, "failed", error_message=str(exc))


def delete_source(source_id: str) -> None:
    """
    Per spec Section 7.4: deletes a source, its chunks, and the
    corresponding FTS rows. After this, the AI can no longer retrieve
    that content (acceptance criterion #9).
    """
    with transaction() as conn:
        rows = conn.execute(
            "SELECT rowid FROM chunks WHERE source_id = ?", (source_id,)
        ).fetchall()
        rowids = [r["rowid"] for r in rows]

        # ORDERING IS REQUIRED (SPEC §7.7): chunks_fts is an external-content
        # FTS5 table (`content='chunks'`), so deleting an index row reads the
        # content row to determine which terms to remove. DELETE FTS rows
        # FIRST, while the chunks rows still exist; deleting chunks first
        # would silently corrupt the index. Any future bulk/Workspace delete
        # must preserve this order.
        for rowid in rowids:
            conn.execute("DELETE FROM chunks_fts WHERE rowid = ?", (rowid,))

        conn.execute("DELETE FROM chunks WHERE source_id = ?", (source_id,))
        conn.execute("DELETE FROM sources WHERE source_id = ?", (source_id,))


def clear_source_chunks(source_id: str) -> None:
    """
    Delete a source's chunks and their FTS index rows, KEEPING the sources row.
    Used by the §22.6 re-ingestion pass: re-ingestion replaces a source's
    chunks, so the old ones must go first. Preserves the same FTS-before-chunks
    ordering as delete_source() (SPEC §7.7).
    """
    with transaction() as conn:
        rows = conn.execute(
            "SELECT rowid FROM chunks WHERE source_id = ?", (source_id,)
        ).fetchall()
        for row in rows:
            conn.execute("DELETE FROM chunks_fts WHERE rowid = ?", (row["rowid"],))
        conn.execute("DELETE FROM chunks WHERE source_id = ?", (source_id,))


def reingest_source(
    file_path: str, source_type: str, source_id: str, workspace_id: str
) -> None:
    """
    SPEC §22.6: replace one source's index from its already-stored bytes. Clears
    the source's existing chunks (keeping the sources row and its identity),
    then runs ingest_source() afresh. It reads the given file path and does not
    touch anything else under data/.
    """
    clear_source_chunks(source_id)
    ingest_source(file_path, source_type, source_id, workspace_id)


def _set_status(source_id: str, status: str, error_message: str | None = None) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE sources SET status = ?, error_message = ? WHERE source_id = ?",
            (status, error_message, source_id),
        )


def _sync_fts(conn, source_id: str) -> None:
    """
    Re-populate chunks_fts for the rows just inserted for this source.
    Per spec: triggers are a nice-to-have, not required — direct
    re-population after each ingestion batch is acceptable for PoC scale.
    """
    rows = conn.execute(
        "SELECT rowid, text, section_title FROM chunks WHERE source_id = ?",
        (source_id,),
    ).fetchall()
    for row in rows:
        conn.execute(
            "INSERT INTO chunks_fts (rowid, text, section_title) VALUES (?, ?, ?)",
            (row["rowid"], row["text"], row["section_title"]),
        )

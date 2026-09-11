"""
hybrid_search.py — combines lexical (FTS5) and semantic (embedding) retrieval.

Per spec Section 8: hybrid is non-negotiable, not an enhancement to skip.
FTS5 alone misses paraphrases ("manager approve this exception" won't match
"delegated authority for policy deviations" — zero shared words). Semantic
search covers that gap.

hybrid_search() is the ONLY retrieval function the chat flow (Section 9)
should call — never call lexical_search or semantic_search directly from
UI code (Section 8.3).
"""

from __future__ import annotations

import numpy as np

from db import get_connection
from ingestion.embedding import cosine_similarity, vector_from_blob
from ingestion.embedding import _get_model as _get_embedding_model


def lexical_search(question: str, workspace_id: str, top_k: int = 10) -> list[dict]:
    """
    FTS5 with the Porter tokenizer (stemming, no synonym matching — a known,
    accepted limitation, see spec Section 8.1). FTS5 MATCH syntax treats
    certain characters specially; a naive pass-through of user text can raise
    a syntax error, so we quote the query defensively.
    """
    conn = get_connection()
    try:
        fts_query = _sanitize_fts_query(question)
        if not fts_query:
            return []
        rows = conn.execute(
            """
            SELECT chunks.chunk_id, chunks.text, chunks.section_title,
                   chunks.source_id, sources.display_name,
                   chunks_fts.rank AS rank
            FROM chunks_fts
            JOIN chunks ON chunks.rowid = chunks_fts.rowid
            JOIN sources ON sources.source_id = chunks.source_id
            WHERE chunks_fts MATCH ? AND chunks.workspace_id = ?
            ORDER BY chunks_fts.rank
            LIMIT ?
            """,
            (fts_query, workspace_id, top_k),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _sanitize_fts_query(question: str) -> str:
    """
    Wrap each token in double quotes so FTS5 treats them as literal terms
    (an OR-of-terms query), avoiding FTS5 query-syntax errors from
    punctuation in free-form user questions. Simple and PoC-appropriate.
    """
    tokens = [t for t in question.replace('"', " ").split() if t.strip()]
    if not tokens:
        return ""
    return " OR ".join(f'"{t}"' for t in tokens)


def semantic_search(question: str, workspace_id: str, top_k: int = 10) -> list[dict]:
    """
    Brute-force cosine similarity over the Workspace's chunk embeddings.
    Intentionally simple per Section 8.2 — no FAISS/ANN/vector DB, because
    at PoC scale (low thousands of chunks per Workspace) brute-force is
    fast enough.
    """
    conn = get_connection()
    try:
        model = _get_embedding_model()
        q_vector = model.encode(question).astype("float32")

        rows = conn.execute(
            """
            SELECT chunks.chunk_id, chunks.text, chunks.section_title,
                   chunks.source_id, chunks.embedding, sources.display_name
            FROM chunks
            JOIN sources ON sources.source_id = chunks.source_id
            WHERE chunks.workspace_id = ? AND chunks.embedding IS NOT NULL
            """,
            (workspace_id,),
        ).fetchall()

        scored = []
        for row in rows:
            chunk_vector = vector_from_blob(row["embedding"])
            score = cosine_similarity(q_vector, chunk_vector)
            scored.append((score, dict(row)))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:top_k]]
    finally:
        conn.close()


def hybrid_search(
    question: str,
    workspace_id: str,
    top_k: int = 5,
    rrf_k: int = 60,
    candidate_pool: int = 10,
) -> tuple[list[dict], bool]:
    """
    Merges lexical + semantic results via Reciprocal Rank Fusion.

    Returns (chunks, degraded): `chunks` is the merged top-k list; `degraded`
    is True when semantic_search was unavailable and the results are
    lexical-only (SPEC §7.3). On degrade the caller must surface a visible
    note that semantic retrieval is unavailable — this signal is the specified
    exception-free way to do that without importing Streamlit into retrieval/.
    If lexical_search ALSO fails, that exception propagates unchanged (it is
    not part of the degrade path — see §7.3).

    rrf_k=60 and candidate_pool=10 are exposed as parameters (not inline
    magic numbers) specifically so they can be tuned during the Section 11a
    offline evaluation without a code change. RRF is the converged industry
    default for combining differently-scaled rankers without normalization
    (used as-is by OpenSearch, Elasticsearch, Azure AI Search, Weaviate,
    MongoDB Atlas, Qdrant); k in [40, 80] performs comparably per the
    broader literature (Section 16.4).
    """
    lexical = lexical_search(question, workspace_id, top_k=candidate_pool)
    try:
        semantic = semantic_search(question, workspace_id, top_k=candidate_pool)
    except Exception:  # noqa: BLE001 - degrade, see §7.3
        semantic = []
        degraded = True
    else:
        degraded = False

    scores: dict[str, dict] = {}
    for rank, chunk in enumerate(lexical):
        entry = scores.setdefault(chunk["chunk_id"], {"chunk": chunk, "score": 0.0})
        entry["score"] += 1 / (rrf_k + rank)
    for rank, chunk in enumerate(semantic):
        entry = scores.setdefault(chunk["chunk_id"], {"chunk": chunk, "score": 0.0})
        entry["score"] += 1 / (rrf_k + rank)

    ranked = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
    return [r["chunk"] for r in ranked[:top_k]], degraded

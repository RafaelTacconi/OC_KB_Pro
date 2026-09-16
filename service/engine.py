"""
service/engine.py — the shared answer pipeline for the staging API (SPEC §20.9).

Reuses retrieval/, prompting/, and models/ exactly as the Streamlit chat does.
No Streamlit import; no duplicated retrieval/prompt logic. It returns the answer
and structured sources, or raises ServiceError with the HTTP-relevant code and a
`metrics` dict so the caller can write the Tier 1 row (SPEC §19).

Tier 1 logging itself happens in service/api.process_request, which logs exactly
one row per request for every path (answered / refused / error).
"""

from __future__ import annotations

import time

from db import chunk_pages, get_connection
from models.registry import DEFAULT_MODEL_ID, list_models, provider_model_name
from models.router import call_model
from prompting.assemble import build_prompt
from retrieval.hybrid_search import hybrid_search

# The documented refusal (SPEC §20.5, §20.12). Produced by the application, not
# the model, when retrieval returns nothing — no model call, no fabrication.
REFUSAL_TEXT = "The available documents do not cover this question."


class ServiceError(Exception):
    """An error that maps to a documented HTTP status/code (SPEC §20.6)."""

    def __init__(self, status: int, code: str, message: str, metrics: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.metrics = metrics or {}


def _load_workspace(workspace_id: str) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM workspaces WHERE workspace_id = ?", (workspace_id,)
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def _metrics(question: str) -> dict:
    return {
        "question_chars": len(question),
        "chunks_retrieved": 0,
        "lexical_degrade": False,
        "model_slug": None,
        "retrieval_ms": None,
        "total_ms": None,
    }


def _resolve_model(model_id: str | None, metrics: dict) -> str:
    configured = [m.model_id for m in list_models()]
    if not configured:
        raise ServiceError(
            503, "model_unavailable", "No AI model is configured on the service.", metrics
        )
    if model_id is None:
        chosen = DEFAULT_MODEL_ID if DEFAULT_MODEL_ID in configured else configured[0]
    elif model_id in configured:
        chosen = model_id
    else:
        raise ServiceError(
            400, "invalid_request", f"Unknown or unconfigured model {model_id!r}.", metrics
        )
    metrics["model_slug"] = provider_model_name(chosen)
    return chosen


def answer_question(
    workspace_id: str,
    question: str,
    model_id: str | None = None,
    requester: str = "kb_api",
) -> dict:
    """
    Run one question through the existing retrieval -> prompt -> model pipeline.

    Returns {"answer", "sources", "outcome", "metrics"}. Raises ServiceError for
    every documented failure (unknown workspace, no/unconfigured model, provider
    failure) with `metrics` populated as far as it got.
    """
    started = time.perf_counter()
    metrics = _metrics(question)

    workspace = _load_workspace(workspace_id)
    if not workspace:
        metrics["total_ms"] = (time.perf_counter() - started) * 1000.0
        raise ServiceError(404, "workspace_not_found", "Unknown workspace.", metrics)

    chosen = _resolve_model(model_id, metrics)

    t0 = time.perf_counter()
    chunks, degraded = hybrid_search(question, workspace_id, top_k=5)
    metrics["retrieval_ms"] = (time.perf_counter() - t0) * 1000.0
    metrics["chunks_retrieved"] = len(chunks)
    metrics["lexical_degrade"] = degraded

    # SPEC §22.4 / A72: PDF sources carry the stored page number; formats that do
    # not support a page (DOCX/XLSX) — and pre-re-ingestion rows — stay null.
    # The page is read here, not in retrieval/, so no retrieval query changes.
    pages = chunk_pages([c["chunk_id"] for c in chunks])
    sources = [
        {
            "document": c.get("display_name"),
            "section": c.get("section_title"),
            "page": pages.get(c["chunk_id"]),
        }
        for c in chunks
    ]

    if not chunks:
        metrics["total_ms"] = (time.perf_counter() - started) * 1000.0
        return {
            "answer": REFUSAL_TEXT,
            "sources": [],
            "outcome": "refused",
            "metrics": metrics,
        }

    prompt = build_prompt(
        workspace_instructions=workspace.get("instructions", ""),
        retrieved_chunks=chunks,
        user_input=question,
        task_prompt=None,
        model_id=chosen,
    )
    try:
        answer_text = call_model(prompt, model_id=chosen)
    except Exception as exc:  # noqa: BLE001 - provider failures are 502 (§20.6)
        metrics["total_ms"] = (time.perf_counter() - started) * 1000.0
        raise ServiceError(
            502, "provider_error", "The model provider failed to answer.", metrics
        ) from exc

    metrics["total_ms"] = (time.perf_counter() - started) * 1000.0
    return {
        "answer": answer_text,
        "sources": sources,
        "outcome": "answered",
        "metrics": metrics,
    }

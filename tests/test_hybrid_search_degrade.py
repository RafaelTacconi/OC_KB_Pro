"""
test_hybrid_search_degrade.py — SPEC.md §7.3 regression tests.

hybrid_search() must degrade to lexical-only results when semantic search is
unavailable, and say so via its return value — it must NOT crash the turn and
must NOT silently pass off lexical-only results as full hybrid results
(A15). A lexical_search failure is not part of the degrade path and must
propagate to the caller's error handler (§7.3).

These tests monkeypatch the two sub-searches, so no DB or embedding model is
needed.
"""

from __future__ import annotations

import pytest

from retrieval import hybrid_search as module


def _chunk(chunk_id: str, display_name: str = "Policy.pdf") -> dict:
    return {
        "chunk_id": chunk_id,
        "source_id": f"source-{chunk_id}",
        "text": f"text of {chunk_id}",
        "section_title": None,
        "display_name": display_name,
    }


def test_hybrid_search_degrades_to_lexical_when_semantic_fails(monkeypatch):
    lexical = [_chunk("c1"), _chunk("c2", "Procedures.pdf")]
    monkeypatch.setattr(module, "lexical_search", lambda *a, **k: lexical)

    def _semantic_boom(*a, **k):
        raise RuntimeError("embedding model unavailable")

    monkeypatch.setattr(module, "semantic_search", _semantic_boom)

    chunks, degraded = module.hybrid_search("question", "workspace-1")
    assert [c["chunk_id"] for c in chunks] == ["c1", "c2"]
    assert degraded is True


def test_hybrid_search_reports_full_merge_when_semantic_available(monkeypatch):
    lexical = [_chunk("c1")]
    semantic = [_chunk("c2", "Procedures.pdf")]
    monkeypatch.setattr(module, "lexical_search", lambda *a, **k: lexical)
    monkeypatch.setattr(module, "semantic_search", lambda *a, **k: semantic)

    chunks, degraded = module.hybrid_search("question", "workspace-1")
    assert {c["chunk_id"] for c in chunks} == {"c1", "c2"}
    assert degraded is False


def test_hybrid_search_lexical_failure_still_propagates(monkeypatch):
    def _lexical_boom(*a, **k):
        raise RuntimeError("FTS error")

    monkeypatch.setattr(module, "lexical_search", _lexical_boom)
    monkeypatch.setattr(module, "semantic_search", lambda *a, **k: [])

    with pytest.raises(RuntimeError, match="FTS error"):
        module.hybrid_search("question", "workspace-1")
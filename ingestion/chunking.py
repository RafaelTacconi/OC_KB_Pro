"""
chunking.py — splits normalized plain text into chunks for indexing.

Per spec Section 7.3 (v2): target ~350-500 tokens, paragraph/heading-boundary
preferred, zero overlap by default (Section 16.3: a Jan-2026 SPLADE + Mistral-8B
analysis on Natural Questions found overlap gave no measurable benefit for the
added indexing cost). Token count is approximated as word_count * 1.3.

Known accepted edge case (carried from v1): a single paragraph longer than
target_tokens (common in XLSX sheet dumps) produces one oversized chunk rather
than being split mid-paragraph. Do not "fix" this without evidence from
Section 11a testing that it causes real retrieval misses.
"""

from __future__ import annotations

# WORDS_TO_TOKENS and estimate_tokens are defined once in models/context_budget.py
# (SPEC §7.8) and imported here. chunk_text keeps its own FRACTIONAL
# per-paragraph accumulation using WORDS_TO_TOKENS and casts once at finalize —
# switching to per-paragraph integer rounding here would shift chunk boundaries.
from models.context_budget import WORDS_TO_TOKENS, estimate_tokens

__all__ = ["WORDS_TO_TOKENS", "estimate_tokens", "chunk_text", "build_embedding_text"]


def chunk_text(
    text: str,
    section_title: str | None = None,
    target_tokens: int = 400,
) -> list[dict]:
    """
    Paragraph-based chunker. Splits on blank-line-separated paragraphs and
    accumulates them until adding the next paragraph would exceed
    target_tokens, then starts a new chunk. No overlap between chunks.

    Returns a list of dicts: {text, section_title, token_count}
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[dict] = []
    current: list[str] = []
    current_tokens = 0.0

    for para in paragraphs:
        para_tokens = len(para.split()) * WORDS_TO_TOKENS
        if current_tokens + para_tokens > target_tokens and current:
            chunks.append(_finalize(current, section_title, current_tokens))
            current = []
            current_tokens = 0.0
        current.append(para)
        current_tokens += para_tokens

    if current:
        chunks.append(_finalize(current, section_title, current_tokens))

    return chunks


def _finalize(paragraphs: list[str], section_title: str | None, token_count: float) -> dict:
    return {
        "text": "\n\n".join(paragraphs),
        "section_title": section_title,
        "token_count": int(token_count),
    }


def build_embedding_text(chunk: dict, max_words: int = 150) -> str:
    """
    Section 8.2a, Option A (the spec's recommended default): embed a short
    representative excerpt rather than the full chunk, because
    all-MiniLM-L6-v2 is trained/evaluated on ~128-256 token inputs and
    silently truncates/degrades beyond that. The full chunk text is still
    what gets sent to the LLM once retrieved (chunks.text) — only the
    *embedding input* is shortened (chunks.embedding_text).
    """
    section = chunk.get("section_title") or ""
    excerpt = " ".join(chunk["text"].split()[:max_words])
    return f"{section}\n{excerpt}".strip()

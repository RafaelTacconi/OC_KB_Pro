"""
embedding.py — local sentence-transformers embeddings, no external API call.

Per spec Section 8.2: all-MiniLM-L6-v2, CPU-only, ~5-14k sentences/sec.
Per spec Section 8.2a: the model is trained/evaluated on ~128-256 token
inputs (confirmed via the model's own sentence_bert_config.json, which
caps max_seq_length at 256 regardless of the tokenizer's 512 limit —
longer inputs are silently truncated, not rejected). A 350-500 token
chunk sent whole to .encode() would be silently truncated at the model
level. This module therefore only ever embeds `embedding_text` (the
short excerpt built in chunking.build_embedding_text), never the full
chunk `text`.
"""

from __future__ import annotations

import numpy as np

_MODEL_NAME = "all-MiniLM-L6-v2"
_model = None  # lazy singleton — loading is not free, avoid reloading per call


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed_text(text: str) -> bytes:
    """Encode a single short string (embedding_text, not full chunk text)."""
    vector = _get_model().encode(text).astype("float32")
    return vector.tobytes()


def embed_batch(texts: list[str]) -> list[bytes]:
    """Batch-encode for ingestion throughput. Order-preserving."""
    if not texts:
        return []
    vectors = _get_model().encode(texts).astype("float32")
    return [v.tobytes() for v in vectors]


def vector_from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype="float32")


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b) + 1e-8
    return float(np.dot(a, b) / denom)

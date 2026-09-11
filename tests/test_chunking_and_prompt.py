"""
test_chunking_and_prompt.py — fast unit tests, no DB / no ML model loading.

Run with: python -m pytest tests/test_chunking_and_prompt.py -v
"""

from __future__ import annotations

from ingestion.chunking import build_embedding_text, chunk_text, estimate_tokens
from prompting.assemble import SYSTEM_POLICY, build_prompt


def test_chunk_text_respects_target_size():
    # 10 paragraphs of ~50 tokens each (~38 words * 1.3) should split into
    # multiple chunks under a 400-token target, not one giant chunk.
    para = " ".join(["word"] * 38)
    text = "\n\n".join([para] * 10)
    chunks = chunk_text(text, section_title="Test Section", target_tokens=400)

    assert len(chunks) > 1
    for c in chunks:
        assert c["token_count"] <= 400 + 60  # allow last paragraph to slightly overshoot
        assert c["section_title"] == "Test Section"


def test_chunk_text_no_overlap():
    para_a = "Alpha paragraph unique content here."
    para_b = "Beta paragraph different unique content."
    text = f"{para_a}\n\n{para_b}"
    chunks = chunk_text(text, target_tokens=1)  # forces a split after first paragraph

    # No paragraph should appear in more than one chunk (zero overlap, Section 16.3).
    all_texts = [c["text"] for c in chunks]
    assert sum(para_a in t for t in all_texts) == 1
    assert sum(para_b in t for t in all_texts) == 1


def test_oversized_single_paragraph_not_split():
    # Known accepted edge case (Section 7.3): one long paragraph -> one
    # oversized chunk, not split mid-paragraph.
    long_para = " ".join(["word"] * 1000)
    chunks = chunk_text(long_para, target_tokens=400)
    assert len(chunks) == 1
    assert chunks[0]["token_count"] > 400


def test_build_embedding_text_stays_short():
    chunk = {
        "text": " ".join(["word"] * 1000),
        "section_title": "Escalation Procedure",
    }
    embedding_text = build_embedding_text(chunk, max_words=150)
    word_count = len(embedding_text.split())
    # Should be well under all-MiniLM-L6-v2's effective 256-token limit
    # (Section 8.2a) — 150 words + a short section title is safely inside it.
    assert word_count <= 160
    assert "Escalation Procedure" in embedding_text


def test_build_prompt_assembly_order():
    chunks = [
        {"text": "Escalate within 12 hours.", "display_name": "AML_Policy.pdf",
         "section_title": "4.2", "token_count": 10},
    ]
    prompt = build_prompt(
        workspace_instructions="Be concise.",
        retrieved_chunks=chunks,
        user_input="What is the escalation window?",
        task_prompt=None,
    )
    # Fixed order per Section 9.1: system policy, then instructions, then
    # knowledge, then user input.
    assert prompt.index(SYSTEM_POLICY) < prompt.index("Be concise.")
    assert prompt.index("Be concise.") < prompt.index("Available knowledge")
    assert prompt.index("Available knowledge") < prompt.index("User input")
    assert "AML_Policy.pdf" in prompt
    assert "Escalate within 12 hours." in prompt


def test_build_prompt_respects_token_budget():
    # Two chunks, each just under the 3000-token budget on their own —
    # only the first should be included.
    big_chunk_text = " ".join(["word"] * 2000)  # ~2600 tokens
    chunks = [
        {"text": big_chunk_text, "display_name": "A.pdf", "section_title": None,
         "token_count": 2600},
        {"text": big_chunk_text, "display_name": "B.pdf", "section_title": None,
         "token_count": 2600},
    ]
    prompt = build_prompt(
        workspace_instructions="",
        retrieved_chunks=chunks,
        user_input="question",
    )
    assert "A.pdf" in prompt
    assert "B.pdf" not in prompt


def test_estimate_tokens_heuristic():
    assert estimate_tokens("one two three four") == int(4 * 1.3)

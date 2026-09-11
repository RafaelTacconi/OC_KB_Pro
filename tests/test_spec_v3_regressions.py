"""
test_spec_v3_regressions.py — regression tests added alongside SPEC.md (v3).

Run with: python -m pytest tests/test_spec_v3_regressions.py -v

IMPORTANT FOR THE IMPLEMENTING AGENT:
    The test in this file is EXPECTED TO FAIL against the baseline code.
    It is the executable definition of acceptance criterion A14 (SPEC.md §10)
    and it is red on purpose. Do not delete it, weaken it, or mark it skipped.
    Fix SPEC.md §7.2 (`break` -> `continue` in prompting/assemble.py) and it
    turns green.

    The existing tests in test_chunking_and_prompt.py must stay green while
    you do it — in particular test_build_prompt_respects_token_budget, which
    still passes under `continue` because both of its chunks are 2600 tokens
    and neither fits alongside the other.
"""

from __future__ import annotations

from prompting.assemble import build_prompt


def test_oversized_chunk_does_not_discard_smaller_relevant_chunks():
    """
    SPEC.md §7.2 / acceptance criterion A14.

    An oversized top-ranked chunk (the accepted "one XLSX sheet dump -> one
    oversized chunk" behaviour documented in ingestion/chunking.py) must be
    SKIPPED, not treated as a stop signal. Lower-ranked chunks that do fit the
    MAX_RETRIEVED_TOKENS budget must still reach the prompt.

    Baseline behaviour (the bug): `break` exits the loop on the first chunk
    that would overflow the budget, so the knowledge block comes back EMPTY
    and the model is asked to answer with zero grounding.
    """
    oversized = {
        "text": " ".join(["word"] * 4000),  # ~5200 tokens, well over the 3000 budget
        "display_name": "BigSheet.xlsx",
        "section_title": "Sheet1",
        "token_count": 5200,
    }
    small_a = {
        "text": "Escalate within 12 hours.",
        "display_name": "AML_Policy.pdf",
        "section_title": "4.2 Escalation",
        "token_count": 10,
    }
    small_b = {
        "text": "Approval authority sits with the MLRO.",
        "display_name": "AML_Policy.pdf",
        "section_title": "4.3 Approval",
        "token_count": 10,
    }

    prompt = build_prompt(
        workspace_instructions="",
        retrieved_chunks=[oversized, small_a, small_b],
        user_input="What is the escalation window?",
    )

    # The oversized chunk is correctly excluded (it alone blows the budget)...
    assert "BigSheet.xlsx" not in prompt
    # ...but it must not take the two small, relevant chunks down with it.
    assert "Escalate within 12 hours." in prompt
    assert "Approval authority sits with the MLRO." in prompt

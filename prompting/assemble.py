"""
assemble.py — centrally-owned prompt construction (spec Section 9).

"The application owns prompt construction centrally — no individual user or
task should be able to bypass this assembly logic." This is the only place
that builds the final string sent to call_model(). UI code should call
build_prompt(), never concatenate prompt pieces itself.
"""

from __future__ import annotations

from models.context_budget import (
    MAX_RETRIEVED_TOKENS,
    estimate_tokens,
    fits_in_context,
)
from models.registry import get_model_spec

SYSTEM_POLICY = (
    "Always cite the source (file name, and section if available) for any "
    "claim drawn from the provided knowledge. If the available knowledge "
    "does not support an answer, say so explicitly rather than guessing."
)


def build_prompt(
    workspace_instructions: str,
    retrieved_chunks: list[dict],
    user_input: str,
    task_prompt: str | None = None,
    model_id: str | None = None,
) -> str:
    """
    Fixed assembly order (Section 9.1):
      System policy + Workspace Instructions [+ task prompt] + retrieved
      knowledge + user input.

    retrieved_chunks: output of retrieval.hybrid_search.hybrid_search(),
        each a dict with at least {text, display_name, section_title,
        token_count?}.
    model_id: if given, used only to sanity-check the assembled prompt
        against that model's context window (fits_in_context) — this does
        not change which chunks are included; MAX_RETRIEVED_TOKENS already
        governs that regardless of which model is selected (see
        models/context_budget.py for why the two are kept independent).
    """
    knowledge_block = ""
    token_count = 0
    for chunk in retrieved_chunks:
        chunk_tokens = chunk.get("token_count") or estimate_tokens(chunk["text"])
        if token_count + chunk_tokens > MAX_RETRIEVED_TOKENS:
            # continue, not break (SPEC.md §7.2 / A14): an over-budget chunk
            # is skipped, but lower-ranked smaller chunks that DO fit must
            # still be considered. `break` abandoned the whole loop on the
            # first oversized chunk, leaving the knowledge block empty.
            continue
        knowledge_block += f"\n---\nSource: {chunk['display_name']}"
        if chunk.get("section_title"):
            knowledge_block += f" — {chunk['section_title']}"
        knowledge_block += f"\n{chunk['text']}\n"
        token_count += chunk_tokens

    parts = [SYSTEM_POLICY, workspace_instructions]
    if task_prompt:
        parts.append(task_prompt)
    parts.append(f"Available knowledge:\n{knowledge_block}")
    parts.append(f"User input:\n{user_input}")
    prompt = "\n\n".join(parts)

    if model_id:
        spec = get_model_spec(model_id)
        total_tokens = estimate_tokens(prompt)
        if not fits_in_context(total_tokens, spec.context_window_tokens):
            raise ValueError(
                f"Assembled prompt (~{total_tokens} tokens) does not fit in "
                f"{spec.display_name}'s context window "
                f"({spec.context_window_tokens} tokens) with response headroom. "
                f"This is unusual at this app's normal chunk/task-prompt sizes — "
                f"check for an unusually large task prompt or pasted user input."
            )

    return prompt

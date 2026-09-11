"""
context_budget.py — how many retrieved-chunk tokens go into a prompt.

Per spec Section 9.2: MAX_RETRIEVED_TOKENS=3000 is a *retrieval quality*
ceiling, not a hardware limit — at top_k=5 and 350-500 token chunks, five
chunks land comfortably under it with room to spare (the budget is a safety
ceiling, rarely hit in practice at these settings).

Selectable models here report ~256,000 token context windows (models/registry.py).
That is roughly 85x the retrieval budget. Deliberately do NOT scale
MAX_RETRIEVED_TOKENS up to "use the whole window because it's available":
retrieval quality research this spec already cites (Section 16.2 — Chroma,
Azure, Arize AI 2026 benchmarks) is about *chunk size*, not the count of
chunks stuffed into a prompt, but the same "more isn't free" logic applies
at the prompt-assembly level too — stuffing many marginally-relevant chunks
into a huge window increases the chance the model has to search across
noise to find the grounding it needs, and increases latency/cost per call
for no demonstrated recall benefit at this app's scale (a handful of
documents per Workspace). The large window exists as headroom (long task
prompts, longer user-pasted case text, future larger top_k if Section 11a
evidence supports it), not as an invitation to remove the retrieval ceiling.

If a future task prompt or user input is itself very large (e.g. a long
pasted case file), the budget check in build_prompt() (prompting/assemble.py)
also guards against *that* pushing the total over a model's actual window —
see `fits_in_context()` below, used as a safety check, not a normal-path
constraint.
"""

from __future__ import annotations

MAX_RETRIEVED_TOKENS = 3000  # retrieval-quality ceiling — see module docstring
# Reserve room for system policy, instructions, task prompt, user input, and
# the model's own output, on top of MAX_RETRIEVED_TOKENS. This is generous
# headroom given every selectable model's context window is ~256k.
RESPONSE_RESERVE_TOKENS = 4000


def estimate_tokens(text: str) -> int:
    """Same rough heuristic used everywhere else in the app (Section 7.3/9.2)."""
    return int(len(text.split()) * 1.3)


def fits_in_context(total_prompt_tokens: int, model_context_window: int) -> bool:
    """
    Safety check for the (expected to be rare) case where non-retrieval
    parts of the prompt — a long task prompt, a long pasted user input —
    push the assembled prompt close to a model's actual window.
    """
    return total_prompt_tokens + RESPONSE_RESERVE_TOKENS <= model_context_window

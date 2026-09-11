"""
registry.py — the list of AI models a Workspace user may select in chat.

This extends spec constraint 4 (Section 5): the spec's original
`call_model(prompt: str) -> str` assumed one hardcoded model. The updated
requirement (user can pick the model per question/task) still honors the
constraint's intent — one thin abstraction, no provider SDK calls scattered
through the app — by keeping a single call_model() entry point (models/router.py)
that dispatches on `model_id` using the metadata defined here.

Each entry's `context_window_tokens` reflects the ~256k figure the internal
gateway reports for these models. This number matters directly for Section 9.2:
MAX_RETRIEVED_TOKENS (a fixed 3000-token retrieval budget) is far below any of
these windows, so the ceiling in the spec is a deliberate, conservative
generation-quality choice (keep the model focused on a handful of chunks, not
"use the whole window because it's available") — not a hardware limit. See
models/context_budget.py for how the two interact.

Update this file, not scattered constants elsewhere, when the internal
gateway adds/removes a model or changes its context window.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    model_id: str            # stable key used in DB rows and UI state
    display_name: str        # shown in the model picker
    provider: str            # dispatch key for models/router.py adapters
    provider_model_name: str  # the exact string the provider's API expects
    context_window_tokens: int
    notes: str = ""


# NOTE: provider_model_name values are illustrative placeholders for the
# internal gateway's current model slugs. Confirm exact strings against the
# internal API's model list before wiring this to a live endpoint — do not
# assume these are correct without checking (see build order note in
# ui/model_picker.py).
AVAILABLE_MODELS: list[ModelSpec] = [
    ModelSpec(
        model_id="internal-fast",
        display_name="Fast (low latency)",
        provider="internal_gateway",
        provider_model_name="internal-fast-v1",
        context_window_tokens=256_000,
        notes="Best default for short factual questions and most / tasks.",
    ),
    ModelSpec(
        model_id="internal-standard",
        display_name="Standard",
        provider="internal_gateway",
        provider_model_name="internal-standard-v1",
        context_window_tokens=256_000,
        notes="Balanced default; recommended starting choice.",
    ),
    ModelSpec(
        model_id="internal-reasoning",
        display_name="Reasoning (slower, more thorough)",
        provider="internal_gateway",
        provider_model_name="internal-reasoning-v1",
        context_window_tokens=256_000,
        notes="Use for multi-step analysis tasks, e.g. /analyze-case.",
    ),
]

DEFAULT_MODEL_ID = "internal-standard"

_BY_ID = {m.model_id: m for m in AVAILABLE_MODELS}


def get_model_spec(model_id: str) -> ModelSpec:
    try:
        return _BY_ID[model_id]
    except KeyError as exc:
        raise ValueError(
            f"Unknown model_id {model_id!r}. Available: {list(_BY_ID)}"
        ) from exc


def list_models() -> list[ModelSpec]:
    return list(AVAILABLE_MODELS)

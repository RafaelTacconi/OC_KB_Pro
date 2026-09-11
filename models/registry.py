"""
registry.py — the list of AI models a Workspace user may select in chat.

This extends spec constraint 4 (Section 5): the spec's original
`call_model(prompt: str) -> str` assumed one hardcoded model. The updated
requirement (user can pick the model per question/task) still honors the
constraint's intent — one thin abstraction, no provider SDK calls scattered
through the app — by keeping a single call_model() entry point (models/router.py)
that dispatches on `model_id` using the metadata defined here.

SPEC §14.3 splits responsibility between this file and .env:

  | Lives in .env                    | Lives in models/registry.py       |
  | Base URL                         | model_id (stable DB/UI key)       |
  | API key                          | display_name (shown in picker)    |
  | API key expiry date              | notes (shown beside the picker)   |
  | provider_model_name (endpoint    | context_window_tokens             |
  |   slug)                          |                                   |

The distinction: .env holds what changes between deployments; this registry
holds what the user sees. `provider_model_name(model_id)` reads the slug
lazily from .env — a ModelSpec whose slug env var is empty is OMITTED from
list_models() (SPEC §14.3): never show a model that cannot be called.

Each entry's `context_window_tokens` reflects the ~256k figure the internal
gateway reports for these models. This number matters directly for Section 9.2:
MAX_RETRIEVED_TOKENS (a fixed 3000-token retrieval budget) is far below any of
these windows, so the ceiling in the spec is a deliberate, conservative
generation-quality choice (keep the model focused on a handful of chunks, not
"use the whole window because it's available") — not a hardware limit. See
models/context_budget.py for how the two interact. The 256k figure is STILL an
assumption (OPEN-2, updated not closed) — confirm against the real endpoint
when slugs are live.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# model_id -> .env variable holding that model's endpoint slug (SPEC §14.3).
_SLUG_ENV_VARS = {
    "internal-fast": "OPENAI_MODEL_FAST",
    "internal-standard": "OPENAI_MODEL_STANDARD",
    "internal-reasoning": "OPENAI_MODEL_REASONING",
}


@dataclass(frozen=True)
class ModelSpec:
    model_id: str            # stable key used in DB rows and UI state
    display_name: str        # shown in the model picker
    provider: str            # dispatch key for models/router.py adapters
    context_window_tokens: int
    notes: str = ""


# provider slugs come from .env, not from here (SPEC §14.3). Do not reintroduce
# hardcoded slugs: OPEN-2 is updated, not closed, and .env is the one place the
# deployment-owner edits model wiring.
AVAILABLE_MODELS: list[ModelSpec] = [
    ModelSpec(
        model_id="internal-fast",
        display_name="Fast (low latency)",
        provider="openai_compatible",
        context_window_tokens=256_000,
        notes="Best default for short factual questions and most / tasks.",
    ),
    ModelSpec(
        model_id="internal-standard",
        display_name="Standard",
        provider="openai_compatible",
        context_window_tokens=256_000,
        notes="Balanced default; recommended starting choice.",
    ),
    ModelSpec(
        model_id="internal-reasoning",
        display_name="Reasoning (slower, more thorough)",
        provider="openai_compatible",
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


def provider_model_name(model_id: str) -> str:
    """
    The exact slug the endpoint expects for `model_id`, read LAZILY from
    .env (SPEC §14.2 — never module scope). Returns "" when unset/blank.
    """
    var = _SLUG_ENV_VARS.get(model_id, "")
    if not var:
        return ""
    return os.environ.get(var, "").strip()


def list_models() -> list[ModelSpec]:
    """
    Only models whose .env config is complete (SPEC §14.3 resolution rules).

    A model is omitted unless BOTH the endpoint is configured (base URL + API
    key present — §14.2) and that model's slug env var is set. Never show a
    model that cannot be called: with slugs set but no key/base URL, the list
    is empty and the UI shows the "no model configured" message (A20 covers
    partial config, not only a missing .env). If the default's slug is
    unconfigured, callers must fall back to the first configured model (see
    ui/chat_view.py).
    """
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not base_url or not api_key:
        return []
    return [m for m in AVAILABLE_MODELS if provider_model_name(m.model_id)]
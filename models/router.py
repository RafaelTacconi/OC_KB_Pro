"""
router.py — the thin AI-model call abstraction (spec Section 9.3 / constraint 4).

The spec's constraint 4 says: "The AI-model call must go through a thin
abstraction (one function), even though only one model is used in the PoC.
Do not hardcode a specific provider's SDK calls in multiple places."

Since the app now supports multiple selectable models, that one-function
promise is kept as: exactly one function (`call_model`) that every caller
uses, dispatching internally by provider. If every available model in
models/registry.py happens to share one provider (as they do here — all
routed through one internal gateway), there is exactly one branch. Adding
a second provider later means adding one adapter function here, never
touching callers in retrieval/prompt-assembly/UI code.
"""

from __future__ import annotations

import os

from models.registry import get_model_spec

INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")


def call_model(prompt: str, model_id: str) -> str:
    """
    The ONLY function that should ever call an AI provider's SDK/API.
    No caller should import a provider SDK directly.

    Args:
        prompt: the fully-assembled prompt (see prompting/assemble.py).
        model_id: key into models/registry.AVAILABLE_MODELS, typically
                  whatever the user selected in the model picker.
    """
    spec = get_model_spec(model_id)

    if spec.provider == "internal_gateway":
        return _call_internal_gateway(prompt, spec.provider_model_name)

    raise ValueError(f"No adapter implemented for provider {spec.provider!r}")


def _call_internal_gateway(prompt: str, provider_model_name: str) -> str:
    """
    Adapter for the organization's internal AI-model API.
    Replace the body with the actual internal client call; the interface
    (prompt in, text out) should not need to change for callers.
    """
    if not INTERNAL_API_KEY:
        raise RuntimeError(
            "INTERNAL_API_KEY is not set. Load it from environment/secrets — "
            "never hardcode it (spec Section 9.3)."
        )

    # --- Placeholder call shape; swap for the real internal SDK/HTTP call. ---
    # import internal_ai_client
    # response = internal_ai_client.generate(
    #     api_key=INTERNAL_API_KEY,
    #     model=provider_model_name,
    #     prompt=prompt,
    # )
    # return response.text
    raise NotImplementedError(
        "Wire _call_internal_gateway() to the organization's actual internal "
        "AI-model API before running against real users."
    )

"""
router.py — the thin AI-model call abstraction (spec Section 9.3 / constraint 4).

The spec's constraint 4 says: "The AI-model call must go through a thin
abstraction (one function), even though only one model is used in the PoC.
Do not hardcode a specific provider's SDK calls in multiple places."

Since the app now supports multiple selectable models, that one-function
promise is kept as: exactly one function (`call_model`) that every caller
uses, dispatching internally by provider. If every available model in
models/registry.py happens to share one provider (as they do here — all
routed through one OpenAI-compatible endpoint), there is exactly one branch.
Adding a second provider later means adding one adapter function here, never
touching callers in retrieval/prompt-assembly/UI code.

SPEC §14.2: all environment reads are lazy, inside the function that needs
the value — never at module scope. There is deliberately no module-scope
`os.environ.get(...)` here anymore.
"""

from __future__ import annotations

import os

from models.registry import get_model_spec, provider_model_name

OPENAI_BASE_URL_ENV = "OPENAI_BASE_URL"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"


def call_model(prompt: str, model_id: str) -> str:
    """
    The ONLY function that should ever call an AI provider's SDK/API.
    No caller should import a provider SDK directly.

    Args:
        prompt: the fully-assembled prompt (see prompting/assemble.py).
        model_id: key into models/registry.AVAILABLE_MODELS, typically
                  whatever the user selected in the model picker.

    Signature is unchanged (SPEC §14.4 / A25). Provider exceptions propagate
    to the §7.1 handler — do NOT add error handling here.
    """
    spec = get_model_spec(model_id)

    if spec.provider == "openai_compatible":
        return _call_openai_compatible(prompt, model_id)

    raise ValueError(f"No adapter implemented for provider {spec.provider!r}")


def _call_openai_compatible(prompt: str, model_id: str) -> str:
    """
    Adapter for an OpenAI-compatible endpoint (SPEC §14.4, OPEN-11: a proxy
    / gateway, not Azure).

    The client is constructed inside this function so credentials are read
    lazily and no SDK call is ever made at import time. The model slug comes
    from .env via registry.provider_model_name (the registry holds what the
    user sees; .env holds what the endpoint expects).

    No error handling here on purpose — provider exceptions propagate to the
    §7.1 inline-error-with-retry. Nothing is logged (no prompt, no key).
    """
    from openai import OpenAI

    base_url = os.environ.get(OPENAI_BASE_URL_ENV, "").strip()
    api_key = os.environ.get(OPENAI_API_KEY_ENV, "").strip()
    model = provider_model_name(model_id)

    if not base_url or not api_key or not model:
        raise RuntimeError(
            "Model endpoint is not configured. Copy `.env.example` to `.env` "
            "and set OPENAI_BASE_URL, OPENAI_API_KEY, and the "
            f"OPENAI_MODEL_* slug for {model_id!r} — see SPEC.md §14.2."
        )

    client = OpenAI(base_url=base_url, api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""
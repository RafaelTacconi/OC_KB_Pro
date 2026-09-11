"""
test_provider_config.py — SPEC.md §14 (Addendum A) unit tests.

Covers the registry/.env split (§14.3), the expiry status function (§14.5,
A23), and the router's lazy-config guard. These are pure unit tests with no
DB or Streamlit. UI-level checks (picker fallback, sidebar pills) are covered
by AppTest in test_provider_config_app.py where they need a running app.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from models.credentials import KEY_EXPIRY_WARNING_DAYS, api_key_status
from models.registry import (
    DEFAULT_MODEL_ID,
    get_model_spec,
    list_models,
    provider_model_name,
)
from models.router import call_model


def _env(monkeypatch: pytest.MonkeyPatch, **values: str) -> None:
    for k, v in values.items():
        monkeypatch.setenv(k, v)


def test_list_models_omits_unconfigured_slugs(monkeypatch):
    _env(
        monkeypatch,
        OPENAI_MODEL_FAST="fast-real",
        OPENAI_MODEL_STANDARD="",
        OPENAI_MODEL_REASONING="reason-real",
    )
    ids = [m.model_id for m in list_models()]
    assert ids == ["internal-fast", "internal-reasoning"]


def test_list_models_empty_when_nothing_configured(monkeypatch):
    _env(
        monkeypatch,
        OPENAI_MODEL_FAST="",
        OPENAI_MODEL_STANDARD="",
        OPENAI_MODEL_REASONING="",
    )
    assert list_models() == []


def test_provider_model_name_is_lazy_and_blank_when_unset(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL_FAST", raising=False)
    assert provider_model_name("internal-fast") == ""
    monkeypatch.setenv("OPENAI_MODEL_FAST", "  slug-with-space  ")
    assert provider_model_name("internal-fast") == "slug-with-space"


def test_call_model_raises_clear_runtime_error_when_unconfigured(monkeypatch):
    # No OPENAI_* vars at all: must raise a config message, never pass model_id
    # to the SDK, and never reach credentials of a nonexistent key.
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_MODEL_STANDARD", "std-real")

    with pytest.raises(RuntimeError, match=r"\.env"):
        call_model("hello", DEFAULT_MODEL_ID)


def test_call_model_raises_for_unknown_model(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL_FAST", raising=False)
    with pytest.raises(ValueError, match="Unknown model_id"):
        call_model("hi", "no-such-model")


# --- api_key_status (A23) ------------------------------------------------------


def test_status_ok_when_far_future(monkeypatch):
    future = (date.today() + timedelta(days=30)).isoformat()
    _env(monkeypatch, OPENAI_API_KEY_EXPIRES_ON=future)
    s = api_key_status()
    assert s.state == "ok"
    assert s.days_remaining == 30


def test_status_expiring_within_warning_window(monkeypatch):
    key = date.today() + timedelta(days=10)
    _env(monkeypatch, OPENAI_API_KEY_EXPIRES_ON=key.isoformat())
    s = api_key_status()
    assert s.state == "expiring"
    assert s.days_remaining == 10


def test_status_expiring_at_zero_is_still_usable(monkeypatch):
    _env(monkeypatch, OPENAI_API_KEY_EXPIRES_ON=date.today().isoformat())
    s = api_key_status()
    assert s.state == "expiring"
    assert s.days_remaining == 0


def test_status_expired_when_past(monkeypatch):
    past = (date.today() - timedelta(days=1)).isoformat()
    _env(monkeypatch, OPENAI_API_KEY_EXPIRES_ON=past)
    s = api_key_status()
    assert s.state == "expired"
    assert s.days_remaining == -1


def test_status_boundary_exactly_warning_days(monkeypatch):
    # exactly KEY_EXPIRY_WARNING_DAYS out is still expiring; one more is ok
    _env(
        monkeypatch,
        OPENAI_API_KEY_EXPIRES_ON=(
            date.today() + timedelta(days=KEY_EXPIRY_WARNING_DAYS)
        ).isoformat(),
    )
    assert api_key_status().state == "expiring"
    _env(
        monkeypatch,
        OPENAI_API_KEY_EXPIRES_ON=(
            date.today() + timedelta(days=KEY_EXPIRY_WARNING_DAYS + 1)
        ).isoformat(),
    )
    assert api_key_status().state == "ok"


def test_status_unknown_when_unset_empty_or_malformed(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY_EXPIRES_ON", raising=False)
    assert api_key_status().state == "unknown"

    _env(monkeypatch, OPENAI_API_KEY_EXPIRES_ON="")
    assert api_key_status().state == "unknown"

    _env(monkeypatch, OPENAI_API_KEY_EXPIRES_ON="not-a-date")
    assert api_key_status().state == "unknown"

    _env(monkeypatch, OPENAI_API_KEY_EXPIRES_ON="2026-13-99")
    assert api_key_status().state == "unknown"


def test_status_never_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY_EXPIRES_ON", raising=False)
    api_key_status()  # unset
    _env(monkeypatch, OPENAI_API_KEY_EXPIRES_ON="garbage")
    api_key_status()  # malformed


def test_get_model_spec_still_works_for_unconfigured_id(monkeypatch):
    # Registry metadata is static; list_models() filters for the UI but the
    # spec lookup must not crash for an id that exists but is unconfigured.
    monkeypatch.delenv("OPENAI_MODEL_REASONING", raising=False)
    spec = get_model_spec("internal-reasoning")
    assert spec.context_window_tokens == 256_000
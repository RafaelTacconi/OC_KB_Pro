"""
test_provider_config_app.py — SPEC.md §14 UI-level acceptance (A20, A21, A22).

Runs the real app headlessly via AppTest in a temp cwd (no .env, isolated DB):

  A20 — with no .env, the app starts, Manage works, and the chat surface shows
        the "no model configured" message rather than a stack trace.
  A21 — a configured model appears in the picker; if DEFAULT_MODEL_ID's slug is
        blank, the picker opens on the first configured model without raising.
  A22 — with an expiry date set in the warning window, an Owner sees an orange
        warning in the sidebar; a Member does not (OPEN-12 interim).

Date math uses real today; a warning-window date is computed at test time.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from models.registry import list_models

REPO_ROOT = Path(__file__).resolve().parents[1]


def _env(monkeypatch: pytest.MonkeyPatch, **values: str) -> None:
    for k, v in values.items():
        monkeypatch.setenv(k, v)


def _blank_all_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force an empty model config for the test.

    AppTest.from_file runs app.py with cwd = the repo root, so config.py's
    load_dotenv() would load the real `.env` even though the test chdir's to a
    temp dir. Setting every OPENAI_* var to "" (rather than delenv) makes
    load_dotenv() a no-op for them (it never overrides an existing var), so the
    test really exercises the no-config / partial-config path.
    """
    for k in (
        "OPENAI_BASE_URL",
        "OPENAI_API_KEY",
        "OPENAI_API_KEY_EXPIRES_ON",
        "OPENAI_MODEL_FAST",
        "OPENAI_MODEL_STANDARD",
        "OPENAI_MODEL_REASONING",
    ):
        monkeypatch.setenv(k, "")


def _run_no_model_check(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> AppTest:
    monkeypatch.chdir(tmp_path)
    os.environ["HF_HUB_OFFLINE"] = "1"
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception, list(at.exception)
    assert any("No AI model is configured" in w.value for w in at.warning)
    # A20 (option 1): the send path is BLOCKED, not hidden — chat input and
    # task buttons are disabled so it reads "fix your config", and no send can
    # fail with a raw "Unknown model_id None".
    assert at.chat_input[0].proto.disabled
    for b in at.button:
        if b.key and b.key.startswith("task_btn_"):
            assert b.proto.disabled, f"task button {b.key} should be disabled"

    # Manage still works for the owner.
    at.button(key="nav_manage").click().run()
    assert not at.exception, list(at.exception)
    assert at.radio(key="wa_manage_section").value == "Knowledge"
    return at


def test_a20_no_env_no_stack_trace_and_no_model_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Blank every model var so a real .env on disk cannot leak into the test.
    _blank_all_model_env(monkeypatch)
    _run_no_model_check(monkeypatch, tmp_path)


def test_a20_partial_config_missing_key_or_base_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # SPEC §14.3 partial-config extension (owner request): slugs are set but
    # OPENAI_API_KEY / OPENAI_BASE_URL are blank. The likely first-run state.
    # A model that cannot be called must not be shown, so the SAME clear
    # "no model configured" message appears instead of an inline failure on
    # every send.
    _blank_all_model_env(monkeypatch)
    _env(
        monkeypatch,
        OPENAI_MODEL_FAST="fast-real",
        OPENAI_MODEL_STANDARD="std-real",
        OPENAI_MODEL_REASONING="reason-real",
    )
    assert list_models() == []  # no key or base URL configured yet
    _run_no_model_check(monkeypatch, tmp_path)


def test_a21_picker_filters_and_falls_back_to_first_configured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    os.environ["HF_HUB_OFFLINE"] = "1"
    # DEFAULT_MODEL_ID is internal-standard; leave ITS slug blank so the picker
    # must fall back to the first configured model without crashing. Endpoint
    # must be configured or no model shows at all (§14.3 partial-config).
    _env(
        monkeypatch,
        OPENAI_BASE_URL="http://proxy/v1",
        OPENAI_API_KEY="k",
        OPENAI_MODEL_FAST="fast-real",
        OPENAI_MODEL_STANDARD="",
        OPENAI_MODEL_REASONING="reason-real",
    )

    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    assert not any("No AI model is configured" in w.value for w in at.warning)

    mid = at.selectbox(key="model_picker_aml-workspace")
    # The picker labels include the read-only .env slug (SPEC §14.3 note,
    # owner-approved): "display_name (slug)". The two configured models appear,
    # the blank-slug one does not (A21).
    assert mid.options == [
        "Fast (low latency) (fast-real)",
        "Reasoning (slower, more thorough) (reason-real)",
    ]
    # value is the raw model_id; fallback from the unconfigured
    # DEFAULT_MODEL_ID to the first configured model.
    assert mid.value == "internal-fast"
    assert not at.exception


def test_a22_expiring_warning_owner_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    os.environ["HF_HUB_OFFLINE"] = "1"
    _env(
        monkeypatch,
        OPENAI_MODEL_STANDARD="std-real",
        OPENAI_API_KEY_EXPIRES_ON=(
            date.today() + timedelta(days=10)
        ).isoformat(),
    )

    # Owner (first in TEST_USERS) sees the warning.
    at = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    owner_sees = any("Renew the API key" in c.value for c in at.sidebar.caption)
    assert owner_sees

    # Switch user to a Member: warning must disappear (OPEN-12 interim).
    at.sidebar.selectbox[0].set_value("u_member1").run()
    assert not at.exception
    member_sees = any("Renew the API key" in c.value for c in at.sidebar.caption)
    assert not member_sees
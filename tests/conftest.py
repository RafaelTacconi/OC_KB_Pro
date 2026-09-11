"""
conftest.py — session-wide guardrails for the test suite.

1. Deterministic model config: no test result may depend on the developer's
   local `.env`. AppTest runs the app IN-PROCESS, and config.py's load_dotenv()
   reads `.env` from the process cwd once at import — so a real `.env` on disk
   would otherwise leak into os.environ for the whole session. An autouse
   fixture blanks every OPENAI_*/OPENROUTER_* var before the first test, so
   the suite always starts from a known "no model configured" state unless a
   test opts in explicitly via monkeypatch.setenv (e.g. A21/A22).

2. Mechanical assertion: after the whole suite runs, no `data/` directory may
   exist at the repository root. AppTest tests run in an isolated temp cwd
   (monkeypatch.chdir(tmp_path)) so the SQLite DB and uploaded sources are never
   written into the repo. This makes that invariant explicit rather than
   something caught only by inspection.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

_ENV_VARS = (
    "OPENAI_BASE_URL",
    "OPENAI_API_KEY",
    "OPENAI_API_KEY_EXPIRES_ON",
    "OPENAI_MODEL_FAST",
    "OPENAI_MODEL_STANDARD",
    "OPENAI_MODEL_REASONING",
    "OPENROUTER_API_KEY",
    "OPENROUTER_API_KEY_EXPIRES",
)


@pytest.fixture(scope="session", autouse=True)
def _blank_model_env():
    """
    Blank every model/env/credential var for the ENTIRE session, so AppTest
    tests can never observe the developer's local `.env` (which config.py's
    load_dotenv() would otherwise load in-process). Setting (not deleting)
    means load_dotenv() treats them as already-present and does not override.
    Tests that need a configured model set their own values (monkeypatch).
    """
    saved = {}
    for k in _ENV_VARS:
        saved[k] = os.environ.get(k)
        os.environ[k] = ""
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture()
def configured_model(monkeypatch: pytest.MonkeyPatch):
    """Opt a test into a configured model so the chat input / task buttons are
    ENABLED (they are disabled when no model is set — SPEC §15.2). Tests that
    drive the chat send path request this fixture; the autouse _blank_model_env
    fixture has already blanked all OPENAI_* vars so nothing leaks from the
    developer's .env.

    Semantic: this fixture only sets env vars; it returns None. Tests that also
    stub call_model combine the two (fixture function-scoped, runs first).
    """
    import os

    os.environ["HF_HUB_OFFLINE"] = "1"
    monkeypatch.setenv("OPENAI_BASE_URL", "http://proxy/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("OPENAI_MODEL_FAST", "fast-real")
    monkeypatch.setenv("OPENAI_MODEL_STANDARD", "std-real")
    return None


@pytest.fixture(scope="session", autouse=True)
def _assert_no_repo_data_dir():
    yield
    assert not (REPO_ROOT / "data").exists(), (
        "AppTest left a data/ directory at the repo root — AppTest tests must "
        "run in an isolated temp cwd, never write into the repository."
    )

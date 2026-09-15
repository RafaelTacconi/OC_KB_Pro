"""
conftest.py — session-wide guardrails for the test suite.

1. Deterministic model config: no test result may depend on the developer's
   local `.env`. AppTest runs the app IN-PROCESS, and config.py's load_dotenv()
   reads `.env` from the process cwd once at import — so a real `.env` on disk
   would otherwise leak into os.environ for the whole session. An autouse
   fixture blanks every OPENAI_*/OPENROUTER_* var before the first test, so
   the suite always starts from a known "no model configured" state unless a
   test opts in explicitly via monkeypatch.setenv (e.g. A21/A22).

2. Repo `data/` integrity: the test suite must not write into the repository.
   AppTest tests run in an isolated temp cwd (monkeypatch.chdir(tmp_path)) so
   the SQLite DB and uploaded sources are never written into the repo. The
   guard snapshots `data/` at suite start and asserts it is byte-UNCHANGED at
   the end. This distinguishes pre-existing app data (the running app
   legitimately creates `data/` at the repo root — this is NOT a test leak)
   from test-created files, without weakening anything: a stopped app's `data/`
   passes (snapshot == end state), and any test that creates or modifies a repo
   `data/` file fails the assertion.
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
    # Staging API config (SPEC §20.9-§20.13) — blanked so tests are deterministic
    # and never inherit a developer's real .env.
    "KB_API_KEY",
    "KB_API_HOST",
    "KB_API_PORT",
)


def _repo_data_snapshot() -> dict[str, int] | None:
    """
    {'data/<relpath>': size} for every file under the repo `data/` directory,
    or None if `data/` does not exist. Used to detect whether the TEST SUITE
    (as opposed to the running app, which legitimately owns `data/`) touched
    the repo.
    """
    data = REPO_ROOT / "data"
    if not data.exists():
        return None
    snapshot: dict[str, int] = {}
    for p in sorted(data.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(data)).replace("\\", "/")
            snapshot[rel] = p.stat().st_size
    return snapshot


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
def _assert_repo_data_dir_unchanged():
    """
    Snapshot the repo `data/` before the suite; assert it is UNCHANGED after.
    A stopped app legitimately leaves `data/` in the repo — that is not a test
    leak and must not fail the suite. What must fail: the TEST SUITE creating,
    deleting, or rewriting any file under repo `data/`.
    """
    before = _repo_data_snapshot()
    yield
    after = _repo_data_snapshot()
    assert before == after, (
        "The test suite changed data/ at the repo root — AppTest tests must "
        "run in an isolated temp cwd and never write into the repository. "
        "If data/ is changing, either a test is leaking into the repo or a "
        "live app instance is writing to it during the run; stop the app "
        "before running pytest."
    )

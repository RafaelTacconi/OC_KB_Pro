"""
conftest.py — session-wide guardrails for the test suite.

Mechanical assertion: after the whole suite runs, no `data/` directory may
exist at the repository root. AppTest tests run in an isolated temp cwd
(monkeypatch.chdir(tmp_path)) so the SQLite DB and uploaded sources are never
written into the repo. This makes that invariant explicit rather than
something caught only by inspection.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def _assert_no_repo_data_dir():
    yield
    assert not (REPO_ROOT / "data").exists(), (
        "AppTest left a data/ directory at the repo root — AppTest tests must "
        "run in an isolated temp cwd, never write into the repository."
    )

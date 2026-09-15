"""
test_api_staging.py — staging API guards and error paths (SPEC §20.9-§20.13 /
A56-A61).

These tests never call the live model: every path exercised here fails before the
provider call (auth, malformed, oversized, unknown workspace, no model
configured). The success path needs a live endpoint and is not automated.
"""

from __future__ import annotations

import json

import pytest

from activity_log import get_log_connection
from db import init_db, transaction
from service import api


def test_bind_guard_refuses_non_loopback(monkeypatch):
    monkeypatch.setenv("KB_API_HOST", "0.0.0.0")
    with pytest.raises(SystemExit) as exc:
        api.resolve_host()
    message = str(exc.value)
    assert "OPEN-13" in message and "OPEN-14" in message


def test_bind_guard_refuses_lan_address(monkeypatch):
    monkeypatch.setenv("KB_API_HOST", "192.168.1.10")
    with pytest.raises(SystemExit):
        api.resolve_host()


def test_bind_guard_default_and_loopback_ok(monkeypatch):
    monkeypatch.delenv("KB_API_HOST", raising=False)
    assert api.resolve_host() == "127.0.0.1"
    monkeypatch.setenv("KB_API_HOST", "127.0.0.1")
    assert api.resolve_host() == "127.0.0.1"


def test_resolve_key_refuses_when_unset(monkeypatch):
    monkeypatch.setenv("KB_API_KEY", "")
    with pytest.raises(SystemExit):
        api.resolve_key()


def _rows():
    conn = get_log_connection()  # cwd is tmp_path -> tmp_path/data/logs.db
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM tier1_turn_log")]
    finally:
        conn.close()


def test_missing_key_401_and_still_logged(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    status, body = api.process_request(b"{}", 2, None, "secret")
    assert status == 401
    assert body["error"]["code"] == "unauthenticated"
    rows = _rows()
    assert len(rows) == 1
    assert rows[0]["source"] == "api"
    assert rows[0]["outcome"] == "error"
    assert rows[0]["error_type"] == "unauthenticated"


def test_wrong_key_401(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    status, body = api.process_request(b"{}", 2, "wrong", "secret")
    assert status == 401
    assert body["error"]["code"] == "unauthenticated"


def test_oversized_request_413(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    status, body = api.process_request(b"", api.MAX_REQUEST_BYTES + 1, "secret", "secret")
    assert status == 413
    assert body["error"]["code"] == "invalid_request"


def test_malformed_json_400(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    status, body = api.process_request(b"not-json", 8, "secret", "secret")
    assert status == 400
    assert body["error"]["code"] == "invalid_request"


def test_missing_fields_400(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    raw = json.dumps({"workspace": "w"}).encode()
    status, body = api.process_request(raw, len(raw), "secret", "secret")
    assert status == 400


def test_unknown_workspace_404(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    init_db()
    raw = json.dumps({"workspace": "nope", "question": "hello"}).encode()
    status, body = api.process_request(raw, len(raw), "secret", "secret")
    assert status == 404
    assert body["error"]["code"] == "workspace_not_found"


def test_no_model_configured_503(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    init_db()
    with transaction() as conn:
        conn.execute(
            "INSERT INTO workspaces (workspace_id, name, owner_user_id, instructions, created_at, updated_at) "
            "VALUES ('w', 'W', 'u', '', 'now', 'now')"
        )
    raw = json.dumps({"workspace": "w", "question": "hello"}).encode()
    status, body = api.process_request(raw, len(raw), "secret", "secret")
    assert status == 503
    assert body["error"]["code"] == "model_unavailable"

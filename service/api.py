"""
service/api.py — the staging HTTP service (SPEC.md §20.9-§20.13).

A separate small process using the Python standard library (no new dependency).
It reuses service.engine, which in turn reuses retrieval/, prompting/, and
models/ — no API code lives in the Streamlit app.

Start it with:  python -m service.api

Staging safety is by construction, not policy (SPEC §20.10):
  - it binds to 127.0.0.1 ONLY and refuses to start otherwise;
  - a single static key (KB_API_KEY) authorises callers.
Both are explicitly temporary and superseded before production by §17 F10 and
OPEN-13/OPEN-14. This build does not answer OPEN-13/14/15/16.
"""

from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from dotenv import load_dotenv

from activity_log import init_log_db, log_turn
from service.engine import ServiceError, answer_question

# The API is its own process and does not import config.py, so it must load
# `.env` itself (SPEC §14.2). Without this, KB_API_KEY and the OPENAI_* slugs
# would be invisible to the service.
load_dotenv()

API_PATH = "/v1/answer"
LOOPBACK_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
# 256 KiB — generous for a question, small enough that a pasted document dump is
# rejected rather than silently sent to the model (SPEC §20.12, `invalid_request`).
MAX_REQUEST_BYTES = 256 * 1024

API_KEY_ENV = "KB_API_KEY"
HOST_ENV = "KB_API_HOST"
PORT_ENV = "KB_API_PORT"
REQUESTER = "kb_api"  # the one shared caller; there is no per-caller identity


# --------------------------------------------------------------------------
# Startup guards (unit-testable, no socket needed)
# --------------------------------------------------------------------------

def resolve_host() -> str:
    """The staging API may bind to loopback ONLY (SPEC §20.10). Anything else is
    a hard refusal to start, naming OPEN-13/OPEN-14."""
    host = os.environ.get(HOST_ENV, LOOPBACK_HOST).strip() or LOOPBACK_HOST
    if host != LOOPBACK_HOST:
        raise SystemExit(
            f"Refusing to start: {HOST_ENV}={host!r}. The staging API may bind "
            f"ONLY to {LOOPBACK_HOST}. Loopback-only binding is the access "
            f"control while OPEN-13 (is a gate needed?) and OPEN-14 (does one "
            f"already exist?) are unresolved — see SPEC.md §20.10. It must be "
            f"unreachable from the network by construction, not by policy."
        )
    return host


def resolve_port() -> int:
    raw = os.environ.get(PORT_ENV, str(DEFAULT_PORT)).strip() or str(DEFAULT_PORT)
    try:
        port = int(raw)
    except ValueError:
        raise SystemExit(f"Refusing to start: {PORT_ENV}={raw!r} is not a valid port.")
    if not (1 <= port <= 65535):
        raise SystemExit(f"Refusing to start: {PORT_ENV}={port} is out of range.")
    return port


def resolve_key() -> str:
    """A keyless staging API is useless and unsafe, so refuse to start without
    one (SPEC §20.11)."""
    key = os.environ.get(API_KEY_ENV, "").strip()
    if not key:
        raise SystemExit(
            f"Refusing to start: {API_KEY_ENV} is not set. Add it to `.env` "
            f"(see .env.example). This is a temporary shared secret, not the "
            f"production model — see SPEC.md §20.11."
        )
    return key


# --------------------------------------------------------------------------
# Request handling (pure function — unit-testable without a socket)
# --------------------------------------------------------------------------

def _error(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def _log_api(
    workspace_id: str | None,
    question_chars: int,
    chunks_retrieved: int,
    outcome: str,
    error_type: str | None,
    started: float,
    *,
    lexical_degrade: bool = False,
    model_slug: str | None = None,
    retrieval_ms: float | None = None,
    total_ms: float | None = None,
) -> None:
    if total_ms is None:
        total_ms = (time.perf_counter() - started) * 1000.0
    log_turn(
        "api",
        workspace_id=workspace_id,
        requester=REQUESTER,
        chat_id=None,
        question_chars=question_chars,
        chunks_retrieved=chunks_retrieved,
        lexical_degrade=lexical_degrade,
        model_slug=model_slug,
        retrieval_ms=retrieval_ms,
        total_ms=total_ms,
        outcome=outcome,
        error_type=error_type,
    )


def process_request(
    raw_body: bytes,
    content_length: int | None,
    api_key_header: str | None,
    expected_key: str,
) -> tuple[int, dict]:
    """
    Handle one request and return (http_status, json_body). Writes exactly one
    Tier 1 row for every outcome, including authentication failures (SPEC §19,
    §20.11). Never raises: all failures are documented errors (SPEC §20.6).
    """
    started = time.perf_counter()

    if content_length is not None and content_length > MAX_REQUEST_BYTES:
        _log_api(None, 0, 0, "error", "invalid_request", started)
        return 413, _error("invalid_request", "Request body exceeds the accepted size.")

    if not expected_key or (api_key_header or "") != expected_key:
        _log_api(None, 0, 0, "error", "unauthenticated", started)
        return 401, _error("unauthenticated", "A valid API key header is required.")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:  # noqa: BLE001 - any decode/parse failure is a 400
        _log_api(None, 0, 0, "error", "invalid_request", started)
        return 400, _error("invalid_request", "Request body must be valid JSON.")

    if not isinstance(payload, dict):
        _log_api(None, 0, 0, "error", "invalid_request", started)
        return 400, _error("invalid_request", "Request body must be a JSON object.")

    workspace_id = payload.get("workspace")
    question = payload.get("question")
    model_id = payload.get("model")

    if not isinstance(workspace_id, str) or not workspace_id.strip():
        _log_api(None, 0, 0, "error", "invalid_request", started)
        return 400, _error("invalid_request", "`workspace` is required and must be a string.")
    if not isinstance(question, str) or not question.strip():
        _log_api(workspace_id, 0, 0, "error", "invalid_request", started)
        return 400, _error("invalid_request", "`question` is required and must be a non-empty string.")
    if model_id is not None and not isinstance(model_id, str):
        _log_api(workspace_id, len(question), 0, "error", "invalid_request", started)
        return 400, _error("invalid_request", "`model` must be a string when provided.")

    try:
        result = answer_question(workspace_id, question, model_id=model_id, requester=REQUESTER)
    except ServiceError as exc:
        m = exc.metrics
        _log_api(
            workspace_id,
            m.get("question_chars", len(question)),
            m.get("chunks_retrieved", 0),
            "error",
            exc.code,
            started,
            lexical_degrade=m.get("lexical_degrade", False),
            model_slug=m.get("model_slug"),
            retrieval_ms=m.get("retrieval_ms"),
            total_ms=m.get("total_ms"),
        )
        return exc.status, _error(exc.code, exc.message)

    m = result["metrics"]
    _log_api(
        workspace_id,
        m["question_chars"],
        m["chunks_retrieved"],
        result["outcome"],
        None,
        started,
        lexical_degrade=m["lexical_degrade"],
        model_slug=m["model_slug"],
        retrieval_ms=m["retrieval_ms"],
        total_ms=m["total_ms"],
    )
    return 200, {"answer": result["answer"], "sources": result["sources"]}


# --------------------------------------------------------------------------
# HTTP plumbing
# --------------------------------------------------------------------------

class _Server(ThreadingHTTPServer):
    def __init__(self, addr, handler, expected_key: str):
        super().__init__(addr, handler)
        self.expected_key = expected_key


class _Handler(BaseHTTPRequestHandler):
    server_version = "OC_KB_ProStaging/1.0"

    def do_POST(self):  # noqa: N802 - stdlib naming
        if self.path.split("?", 1)[0] != API_PATH:
            self._send(404, _error("not_found", f"Unknown endpoint. Use POST {API_PATH}."))
            return
        cl = self.headers.get("Content-Length")
        try:
            content_length = int(cl) if cl is not None else None
        except ValueError:
            content_length = None
        if content_length is not None and content_length > MAX_REQUEST_BYTES:
            raw = b""  # refuse without reading the oversized body
        else:
            raw = self.rfile.read(content_length) if content_length else b""
        status, body = process_request(
            raw, content_length, self.headers.get("X-API-Key"), self.server.expected_key
        )
        self._send(status, body)

    def do_GET(self):  # noqa: N802
        self._send(405, _error("method_not_allowed", f"Use POST {API_PATH}."))

    def _send(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args, **kwargs):  # silence per-request stderr noise
        return


def main() -> None:
    host = resolve_host()
    port = resolve_port()
    key = resolve_key()
    init_log_db()
    server = _Server((host, port), _Handler, key)
    print(
        f"OC_KB_Pro staging API on http://{host}:{port}{API_PATH} "
        f"(loopback only; OPEN-13/OPEN-14 unresolved). Ctrl+C to stop."
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
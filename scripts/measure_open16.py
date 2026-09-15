"""
scripts/measure_open16.py — measure OPEN-16 by hand (SPEC.md §11 OPEN-16).

NOT a test. It is deliberately NOT collected by pytest and must never be moved
into tests/. It does not change any retrieval setting.

OPEN-16 asks whether retrieval degrades when case context is pasted into the
question, because the ENTIRE question text becomes the search query. This script
sends the same underlying question to the staging API three ways and prints the
answer and retrieved sources for each, so you can see whether the right documents
still come back as the context grows.

Usage:
    python scripts/measure_open16.py <workspace_id> "your question"

Requires the API running (python -m service.api) and KB_API_KEY in .env. This is
a measurement tool only — it asserts nothing and passes/fails nothing.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv

SHORT_CONTEXT = """Case ref REC-2026-0810. Account 4471-8820-1193 (sort 30-96-17),
customer Hollowbrook Traders Ltd. Break amount GBP 12,480.55, value date
2026-08-10, detected in the overnight reconciliation against the nostro."""

LONG_CONTEXT = """Case ref REC-2026-0810, opened 2026-08-10 by the nostro
reconciliation team. Account 4471-8820-1193 (sort 30-96-17), customer
Hollowbrook Traders Ltd, relationship opened 2019-04-02.

The overnight reconciliation for value date 2026-08-10 returned a break of GBP
12,480.55 between the internal ledger and the correspondent nostro. The item
posted internally at 17:42 on 2026-08-10 with reference INTL-559-882; the nostro
shows no matching credit as of the 06:00 cut-off on 2026-08-11. Two earlier
items of GBP 6,240.28 and GBP 6,240.27 (same counterparty, refs INTL-559-880 and
INTL-559-881) cleared on 2026-08-08 and 2026-08-09 respectively.

The analyst has the customer's payment instruction on file (dated 2026-08-07),
an MT103 confirmation, and a partial refund trace from the correspondent. The
amounts are below the automated investigation threshold but the customer has
asked for a same-day answer because a supplier payment is due 2026-08-12.

At 16:00 on Friday 2026-08-14 the analyst confirmed the funds had not left the
correspondent. The case now needs the procedure that governs how this kind of
reconciliation break is escalated and within what timeframe the customer must be
notified."""


def _post(url: str, key: str, workspace_id: str, question: str) -> tuple[int | None, dict]:
    payload = json.dumps({"workspace": workspace_id, "question": question}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "X-API-Key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(body)
        except Exception:
            return exc.code, {"error": {"code": "http_error", "message": body}}
    except urllib.error.URLError as exc:
        return None, {"error": {"code": "unreachable", "message": str(exc)}}


def _show(label: str, status: int | None, body: dict) -> None:
    print("=" * 78)
    print(label)
    print("-" * 78)
    if status != 200:
        print(f"HTTP {status}: {json.dumps(body.get('error', body), indent=2)}")
        print()
        return
    answer = (body.get("answer") or "").strip()
    print("ANSWER:")
    print(answer if answer else "(empty)")
    print()
    sources = body.get("sources") or []
    print(f"SOURCES ({len(sources)}):")
    if not sources:
        print("  (none — empty retrieval / refusal)")
    for s in sources:
        print(f"  - {s.get('document')} | {s.get('section')} | page={s.get('page')}")
    print()


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    workspace_id, question = argv[1], argv[2]

    load_dotenv()
    key = os.environ.get("KB_API_KEY", "").strip()
    host = os.environ.get("KB_API_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = os.environ.get("KB_API_PORT", "8000").strip() or "8000"
    if not key:
        print("KB_API_KEY is not set in .env — start the API with it set.")
        return 2
    url = f"http://{host}:{port}/v1/answer"

    print(f"Workspace: {workspace_id}")
    print(f"Endpoint : {url}")
    print(f"Question : {question}")
    print()

    cases = [
        ("1. BARE QUESTION", question),
        ("2. SHORT CASE CONTEXT + QUESTION", f"{SHORT_CONTEXT}\n\n{question}"),
        ("3. LONG CASE CONTEXT + QUESTION", f"{LONG_CONTEXT}\n\n{question}"),
    ]
    for label, q in cases:
        status, body = _post(url, key, workspace_id, q)
        _show(label, status, body)
        if status is None:
            print("API unreachable — start it with `python -m service.api` first.")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
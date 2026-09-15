"""
scripts/run_question_set.py — run a bare-question set against the staging API.

NOT a test. It is deliberately NOT collected by pytest and must never be moved
into tests/. It imports nothing from the app and nothing imports it. It changes
no retrieval setting and no prompt.

Companion to scripts/measure_open16.py: that script sends each question three
ways (bare / short context / long context) to measure OPEN-16. This script sends
each question BARE only, so a list of known-answer cases (for example the
GROUNDING_REGRESSION_POSITIVE.md set) can be run and matched back to its cases.
It asserts nothing and passes/fails nothing — correctness is the reader's call.

Usage:
    python scripts/run_question_set.py <workspace_id> <path_to_questions_file>

The questions file is PLAIN TEXT: one question per line. Blank lines and lines
starting with '#' are ignored. It lives off-repo (e.g. on the desktop) and its
path is passed in — this script contains no corpus content and no default path.

Requires the API running (python -m service.api) and KB_API_KEY in .env.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv


def _load_questions(path: str) -> list[str]:
    questions: list[str] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            questions.append(text)
    return questions


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


def _show(index: int, total: int, question: str, status: int | None, body: dict) -> bool:
    """Print one result. Returns True if the API was reachable."""
    print("=" * 78)
    print(f"[{index}/{total}] QUESTION")
    print("-" * 78)
    print(question)
    print()
    if status != 200:
        print(f"HTTP {status}: {json.dumps(body.get('error', body), indent=2)}")
        print()
        return status is not None
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
    return True


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    workspace_id, questions_path = argv[1], argv[2]

    if not os.path.isfile(questions_path):
        print(f"Questions file not found: {questions_path}")
        return 2
    questions = _load_questions(questions_path)
    if not questions:
        print(f"No questions found in: {questions_path}")
        return 2

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
    print(f"Questions: {len(questions)} (from {questions_path})")
    print()

    answered = 0
    refused = 0
    total = len(questions)
    for i, question in enumerate(questions, start=1):
        status, body = _post(url, key, workspace_id, question)
        reachable = _show(i, total, question, status, body)
        if not reachable:
            print("API unreachable — start it with `python -m service.api` first.")
            return 1
        if status == 200:
            if body.get("sources"):
                answered += 1
            else:
                refused += 1

    print("=" * 78)
    print("SUMMARY")
    print("-" * 78)
    print(f"Questions sent : {total}")
    print(f"Answered       : {answered}   (non-empty sources)")
    print(f"Refused        : {refused}   (empty sources)")
    print("(Refusal correctness is NOT judged here — that is the reader's call.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

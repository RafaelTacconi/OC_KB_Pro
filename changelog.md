# changelog.md — what changed

Append-only, newest entry first. One entry per completed build-order step (`SPEC.md` §9), or
per commit if a step spans several. Format and required headings: `SPEC.md` §13.4.

A step with no entry here is not done.

---

## 2026-09-11 — Step 1 — Unblock the app (§7.2 + §7.1)

First implementation step. The app now fails gracefully when the stub model
endpoint raises, instead of crashing to Streamlit's error screen, and no user
message is ever lost.

**Modified**
- `prompting/assemble.py` — `break` → `continue` in the retrieved-chunk loop of
  `build_prompt()`, with a comment at the site citing `SPEC.md` §7.2. An
  over-budget chunk is skipped; smaller lower-ranked chunks still reach the
  prompt (criterion A14, the formerly intentional test failure, is now green).
- `ui/chat_view.py` — §7.1 rework of the answer path:
  - `_answer()` persists the user's message **first** in its own short
    transaction, then runs the turn inside `try/except Exception`.
  - Extracted the retrieval → prompt → model-call → assistant-save pipeline
    into `_run_turn()`, kept free of Streamlit (no `st.spinner` inside).
  - On failure the error is stashed in `st.session_state["wa_pending_error"]`
    (never persisted as an assistant message) and rendered after the rerun as
    an inline assistant bubble — human-readable line, exception text in a
    collapsed `st.expander`, and a Retry button.
  - Retry (`_retry()`) re-runs the same turn from the stored payload without
    re-persisting the user message; a fresh send clears the stash; a
    `(workspace_id, user_id)` guard mismatch clears a stale stash during render.
- `.gitignore` — now ignores runtime `data/` (SQLite DB + uploaded sources),
  created on first run.

**Added**
- `tests/test_chat_error_handling.py` — headless end-to-end regression for
  A12/A13 using `streamlit.testing.v1.AppTest`: sends a message against the
  still-failing stub, asserts the inline error renders, the page survives
  (no exception), the question is persisted exactly once, then clicks Retry and
  asserts it is still exactly one user row with no assistant row.

**Schema and migration changes**
- None. `db.py` schema untouched. The `chats` table is Step 3.

**Acceptance criteria satisfied**
- A12 — failed turn renders inline error, page stays alive, user message
  persisted and visible after rerun.
- A13 — Retry produces one model attempt, never duplicates the user message.
- A14 — oversized chunk skipped, smaller chunks retained.
- A18/A19 — journal maintained as part of this step (see `memory.md`).

**Known-broken / deferred**
- `_call_internal_gateway()` still raises `NotImplementedError` — by design; the
  point of Step 1 was that this fails gracefully now.
- §7.1's "create the `chats` row here too if the Chat is new" is deferred to
  Step 4 (table doesn't exist until Step 3). See `memory.md` deviations.
- Consequence accepted: a failed turn leaves a persisted user message with no
  answer and no retry once the client session ends (retry lives only in session
  state). See `memory.md` deviations.

---

## 2026-09-11 — Step 0 — Baseline package prepared

Specification and project journal added to the original draft. **No application code was
modified**, so every file-and-function reference in `SPEC.md` §7 still points at the real thing.

**Added**
- `SPEC.md` — implementation spec v3: multi-Workspace, multi-Chat, confirmed defects, open
  questions.
- `START_HERE.md` — agent kickoff instructions and rules.
- `AGENTS.md` — short root rules file, loaded automatically by opencode each session.
- `memory.md`, `state.md`, `changelog.md` — project journal (`SPEC.md` §13).
- `tests/test_spec_v3_regressions.py` — regression test for `SPEC.md` §7.2 / criterion A14.
  **Intentionally failing** against this baseline.

**Modified**
- `requirements.txt` — added `pytest>=8.0` under a dev-dependencies comment.
- `README.md` — added a header noting that `SPEC.md` supersedes it. No other edits.

**Schema and migration changes**
- None. The database schema in `db.py` is untouched. Step 3 is the first step that changes it.

**Acceptance criteria satisfied**
- None yet. A18/A19 (journal maintained) begin to apply from the next entry onward.

**Known-broken / deferred**
- Test suite is 7 passed, 1 failed by design — see `state.md`.
- `models/router.py::_call_internal_gateway()` still raises `NotImplementedError`; there is no
  live model endpoint, so no chat turn can succeed end-to-end yet (`SPEC.md` §7.1 is Step 1 for
  exactly this reason).
- All ten `[OPEN]` items unanswered — see `memory.md`.

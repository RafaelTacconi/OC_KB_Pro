# changelog.md — what changed

Append-only, newest entry first. One entry per completed build-order step (`SPEC.md` §9), or
per commit if a step spans several. Format and required headings: `SPEC.md` §13.4.

A step with no entry here is not done.

---

## 2026-09-11 — Step 2 — Resilience (§7.3 + §7.4)

Second implementation step. Chat turns survive an unavailable embedding model
with a visible degrade note, and every destructive delete requires an explicit
second confirmation.

**Modified**
- `retrieval/hybrid_search.py` — `hybrid_search()` now returns
  `(chunks: list[dict], degraded: bool)`. `semantic_search()` runs inside
  `try/except Exception`; on failure the merged result is lexical-only and
  `degraded=True` (SPEC §7.3). A pure `lexical_search()` failure still
  propagates to the `§7.1` handler — it is not part of the degrade path.
- `ui/chat_view.py` — `_run_turn()` returns the degrade flag; `_answer()` and
  `_retry()` clear `wa_semantic_degraded` at the start of a send and set it on
  a successful-but-degraded turn; `render_chat_view()` shows a visible warning
  when it is set ("…lexical (keyword) search only…"). The note survives until
  the next send, mirroring `wa_pending_error`'s lifecycle.
- `ingestion/embedding.py` — `_get_model()` now remembers a FAILED load in
  `_model_load_error` and raises it fast on every later call. Previously each
  call after a failure re-attempted the download; with `§7.3` catching, that
  would have meant a network timeout on every chat turn. Owner-approved
  deviation from prior behaviour — see `memory.md`.
- `ui/owner_view.py` — two-step delete confirmation (SPEC §7.4) for both
  Sources and Tasks via a shared `_render_delete_confirmation()` helper
  (warning naming the item + Confirm delete / Cancel). First click only sets a
  session-state flag keyed by entity id; only "Confirm delete" performs the
  deletion. Task deletion's confirm/cancel renders OUTSIDE the edit form (a
  form's submit buttons can't host the confirm step — the form resets on
  submit). Task expanders and form buttons gained explicit keys so the confirm
  survives the rerun and is testable.
- `tests/offline_retrieval_eval.py` — updated to the new `hybrid_search`
  contract AND made the harness refuse to run degraded: it raises if
  `degraded` is True (owner-directed). A silent fallback would make hybrid and
  lexical-only produce identical rows and falsely suggest hybrid adds nothing.

**Added**
- `tests/test_hybrid_search_degrade.py` — §7.3: semantic failure degrades to
  lexical-only and signals it; both rankers merge cleanly on success; a
  lexical failure still propagates.
- `tests/test_delete_confirmations.py` — A16, end-to-end via AppTest from the
  Manage surface: arming a delete deletes nothing, Cancel dismisses, only
  "Confirm delete" removes the row — for both a Task (seeded) and a Source
  (fake row inserted into the temp DB).

**Schema and migration changes**
- None. `db.py` untouched in this step; the `chats` table and indexes are
  Step 3.

**Acceptance criteria satisfied**
- A15 — a chat turn with the embedding model unavailable yields lexical-only
  results and the UI states semantic retrieval was unavailable (the degrade
  signal + note; full end-to-end still awaits a live model endpoint, which is
  out of scope of this step).
- A16 — deleting a Source or a Task requires an explicit second confirmation
  naming the item.
- A18/A19 — journal maintained (see `memory.md`).

**Known-broken / deferred**
- `_call_internal_gateway()` still raises `NotImplementedError` — by design.
- Embedding model failure is remembered for the session; recovering requires
  an app restart (memory.md deviation).
- The `§7.1` "create the `chats` row" clause remains deferred to Step 4.
- A failed turn still leaves a persisted user message with no answer and no
  retry once the session ends (memory.md deviation).

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

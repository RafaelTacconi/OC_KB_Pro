# changelog.md — what changed

Append-only, newest entry first. One entry per completed build-order step (`SPEC.md` §9), or
per commit if a step spans several. Format and required headings: `SPEC.md` §13.4.

A step with no entry here is not done.

---

## 2026-09-11 — Step 3 + 4 — Schema (chats) + Multi-Chat, landed together

Steps 3 and 4 shipped as ONE commit (owner-delegated decision, agent chose
combined; `memory.md`). Splitting them would have left `_save_message()`
writing `chat_id = NULL` between commits — the exact state A10 forbids. Landing
migration + the Chat features that consume `chat_id` atomically means no
NULL-chat_id window ever exists.

**Schema and migration changes** (Step 3)
- `db.py::SCHEMA` — new `chats` table (SPEC §4.2: `chat_id` PK, `workspace_id`,
  `user_id`, `title`, `created_at`, `updated_at`); `chat_messages` gains
  `chat_id TEXT REFERENCES chats(chat_id)` (nullable at SQL level, enforced
  non-null in app code — §4.3).
- Indexes (SPEC §4.4) moved OUT of `SCHEMA` into a separate `INDEXES` constant,
  so `migrate_db()` can run them AFTER the legacy-`chat_messages` ALTER
  (they reference `chat_id`, which a legacy table does not have yet).
- `db.py::migrate_db()` (SPEC §4.5) — runs SCHEMA first (ensures `chats`
  exists), adds `chat_id` if absent, backfills one `chats` row titled
  "Imported conversation" per distinct `(workspace_id, user_id)` with
  `created_at`/`updated_at` = earliest/latest message, then creates indexes.
  Idempotent; safe on a fresh DB and on a legacy DB alone.
- `config.py::bootstrap()` — calls `migrate_db()` immediately after `init_db()`.

**Multi-Chat** (Step 4)
- `ui/chat_view.py`:
  - `_load_history(chat_id)` — the old `(workspace_id, user_id)` query is
    REMOVED (SPEC §6.3, not kept as fallback).
  - `_save_message()` now takes a required `chat_id` and returns the resolved
    id. When `chat_id` is None (lazy "+ New chat", §6.2) the `chats` row is
    created IN THE SAME transaction, chat first (foreign_keys=ON requires the
    parent before the message → satisfies §7.1 persist-first and item 3).
  - `_load_user_chats(workspace_id, user_id)` ordered by `updated_at DESC`.
  - `_render_chat_row()` — chat selector (labelled by title) + "+ New chat"
    button. `_resolve_active_chat()` validates on every render that `wa_chat_id`
    belongs to the CURRENT (workspace, user) — a stale id from another user or
    Workspace is cleared (Step 3/4 item 1, pre-empts Step 5). First visit
    defaults to the most recent Chat; `wa_chat_id = None` explicitly means
    "new chat pending".
  - `chat_id` threaded through `_run_turn` / `_answer` / `_retry`, and into the
    `wa_pending_error` payload (item 2) so a retry lands in the SAME chat.
  - `_chat_title_from_message()` (OPEN-7 interim titling, §6.2).
  - §6.5 honesty caption (Option A — the assistant has no memory).
- Sidebar user switching is validated against that chat's ownership.

**Tests added**
- `tests/test_migrate_db.py` — builds a LEGACY DB fixture (old schema, no
  `chat_id`), seeds 2 users × 2 workspaces; asserts A10 (one chat per
  (ws,user), no NULL chat_id, correct created/updated, idempotent second run),
  plus a fresh-DB no-op case.
- `tests/test_multi_chat.py` — AppTest with stubbed `call_model`: lazy creation +
  message routing (A7, A8), per-user scoping (A9), workspace scoping (A11), and
  the §6.5 honesty caption.

**Acceptance criteria satisfied**
- A7, A8, A9, A10, A11 (new tests). Plus all prior criteria still green.

**Known-broken / deferred**
- Step 4's "no conversation" empty state shows only for genuinely empty
  threads; a pending new chat with existing threads shows "Starting a new
  conversation." — both satisfy §6.2's allowed lazy option.

---

## 2026-09-11 — Step 2b — Provider configuration and key expiry (SPEC.md §14)

Addendum A, merged as `SPEC.md` §14, implemented. The app can now reach a real
OpenAI-compatible endpoint from `.env` config, wears a dead-simple key-expiry
warning, and starts cleanly with no config at all.

**Added**
- `.env.example` — committed, every variable with an empty value + a short
  comment (base URL, key, expiry date, three model slugs). The file developers
  copy to `.env`.
- `models/credentials.py` — `api_key_status() -> KeyStatus` (frozen dataclass:
  `state` ∈ ok/expiring/expired/unknown, `expires_on`, `days_remaining`).
  Pure computation, no Streamlit, never raises; `KEY_EXPIRY_WARNING_DAYS = 14`;
  UTC date arithmetic; valid through the end of the named day (§14.5).
- `tests/test_provider_config.py` — unit tests for the registry/.env split
  (§14.3), the expiry status boundaries (A23), and the router's lazy config
  guard.
- `tests/test_provider_config_app.py` — AppTest end-to-end for A20 (no .env →
  "no model configured" warning, Manage still works), A21 (picker filters
  blank-slug models and falls back from an unconfigured default without
  raising), A22 (Owner sees the pre-expiry sidebar warning; Member does not,
  per OPEN-12 interim).

**Modified**
- `.gitignore` — ignore `.env` (never commit credentials, §14.2).
- `requirements.txt` — add `python-dotenv>=1.0`, `openai>=1.0`.
- `config.py` — `load_dotenv()` at import (app.py imports config early), so
  lazy reads in `models/` see `.env` values regardless of import order (§14.2).
- `models/router.py` — removed the module-scope
  `INTERNAL_API_KEY = os.environ.get(...)` and the `internal_gateway`
  placeholder. `call_model(prompt, model_id) -> str` signature unchanged
  (A25); dispatches on `provider == "openai_compatible"` to the new
  `_call_openai_compatible()`, which constructs `OpenAI(base_url, api_key)`
  INSIDE the call, reads the slug from `.env`, lets provider exceptions
  propagate to the §7.1 handler, and logs nothing (§14.4). Fails fast with a
  clear `.env` message before the SDK is imported when unconfigured.
- `models/registry.py` — `provider_model_name` is no longer a stored field;
  slugs now come lazily from `.env` via `provider_model_name(model_id)`
  (`_SLUG_ENV_VARS` maps each model_id → its `OPENAI_MODEL_*` env var).
  `list_models()` returns only models whose slug is configured (§14.3);
  `get_model_spec()` unchanged. Provider renamed `internal_gateway` →
  `openai_compatible`.
- `ui/chat_view.py` — `_render_model_picker()` returns `None` when no models
  are configured and shows the "No AI model is configured" warning (A20); falls
  back from `DEFAULT_MODEL_ID` to the first configured model instead of
  raising a `ValueError` (A21). Also dropped the `margin-top: 1.6rem`
  alignment hack on the model note (SP.E.C. §7.8, done early since the line
  was already being touched; the column uses `vertical_alignment="center"`).
- `app.py` — sidebar renders the key status via the existing pill components:
  `expired` (red) to all users, `expiring` (orange) and `unknown` (gray) to
  Owners only (§14.5, OPEN-12 interim). Informational only; never disables
  anything.

**Schema and migration changes**
- None. `db.py` untouched. The `chats` schema work remains Step 3.

**Acceptance criteria satisfied**
- A20, A21, A22, A23 (via the new tests), A24 (`.env` git-ignored;
  `.env.example` committed; nothing real in history), A25
  (`call_model` signature unchanged; `test_chat_error_handling.py` still
  green — it patches `ui.chat_view.call_model`).

**Known-broken / deferred**
- No live endpoint values in this repo, so no real model call was made — the
  adapter is verified fail-fast + wired, but the round-trip needs `.env`
  filled (AGENTS.md "Environment limits").
- `context_window_tokens` still 256k assumption (OPEN-2, updated not closed).
- The `.woff2` font / `static/fonts/README.md` cleanup from §7.8 remains Step 7.

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

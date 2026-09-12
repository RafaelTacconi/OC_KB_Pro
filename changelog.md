# changelog.md — what changed

Append-only, newest entry first. One entry per completed build-order step (`SPEC.md` §9), or
per commit if a step spans several. Format and required headings: `SPEC.md` §13.4.

A step with no entry here is not done.

---

## 2026-09-11 — Offline evaluation result: 15/15 + negative control

Owner ran a hand-built question set against the real corpora (AML, Security
Incident, HR Grievance domains):

- **15 of 15 correct**, plus the negative control (a question with no supporting
  source — answered as "not in the sources", not invented).
- Includes **Q14, a two-step spreadsheet read** (an answer that required
  combining two facts across the XLSX content), which was correct.

This is the first end-to-end evidence that the pipeline (hybrid retrieval →
prompt → live model) produces grounded, correct answers against real
documents. It also surfaced six issues (citation-title quality, chip accuracy/
duplication, history model label, spinner timing) addressed in the entries that
follow.

**Schema and migration changes**
- None.

---

## 2026-09-11 — UI review pass + OPEN-4 closed (per-Workspace membership)

Two owner-directed workstreams after the real-corpus findings.

**UI review pass (items 1–6) + audit fix**
1. Duplicate "Workspace" sidebar label removed (eyebrow is the label).
2. Divider separates the Workspace switcher from `render_brand` (product label
   vs working Workspace no longer read as one block).
3. **API-expiry pill colour was a real bug** (audit): `pill()` looks up the
   class_map by the formatted VALUE, but the map was keyed on the status name,
   so all three expiry branches silently rendered grey. Fixed: key by the exact
   display string — expired→red, expiring→orange, unknown→gray. **Audit
   result:** these were the ONLY three `pill()` call sites keyed on a formatted
   string; all owner_view/source/role maps are correctly keyed on raw values.
4. Chat header now lists the indexed FILE NAMES to every user (Members know
   what they ask against), not just a count; the zero-knowledge message is now
   GREY (design-system pill) not Streamlit-yellow.
5. Model picker (owner-approved, SPEC §14.3 note added): each option shows the
   display_name AND the real .env slug as read-only context
   ("Standard (openai/gpt-4o)"). Registry still owns the label, .env the slug.
6. Task row wraps into rows of up to 4 instead of one `st.columns(n)` — survives
   5/10/20 tasks.

**OPEN-4 closed — per-Workspace membership (level (a))**
- New Workspaces are owned by their creator only (no longer every TEST_USER).
- Manage → Users: Owner can add/remove members per Workspace; the Owner cannot
  be removed.
- `create_workspace()` / `add_member()` / `remove_member()` in config.py.

**Deployment note (OPEN-13, decision 2026-09-11):** authentication is deferred
to the network/reverse-proxy layer in front of the Streamlit port. Until that
gate exists, anyone reaching the port can select "Alex (Owner)" and delete any
knowledge base. Per-Workspace membership does NOT protect against this (it
gates visibility, not identity). Recorded in `state.md`'s Step-8 section and
`memory.md`.

**Tests:** A21 expects slug-suffixed picker labels; A17 checks the grey
markdown note; new `test_task_row_wrap.py` (2), `test_membership.py` (3); A1/A5
updated for owner-only new-Workspace membership. **62 → 67 passed.**

**Schema and migration changes**
- None. `workspace_members` already existed.

---

## 2026-09-11 — §15 work: embedded-image visibility + no-model send block

New work beyond the §14 addendum, per SPEC.md §15 (added 2026-09-11). Two
owner-requested behaviours.

**Added**
- `ingestion/parsers.py::count_embedded_images(file_path, source_type)` — counts
  embedded raster images in a PDF/DOCX using only installed deps (unstructured
  element stream, pypdf XObject scan fallback for PDF; python-docx
  inline_shapes fallback for DOCX). Returns 0 for XLSX and never raises. The
  count is a documented FLOOR (vector/curve-rendered content may not register).
- `ingestion/pipeline.py` — computes `image_count` during `ingest_source` and
  writes it on the `sources` row when indexed.
- `ui/owner_view.py` — Manage → Knowledge shows, per Source with
  `image_count > 0`, a caption "N images — their content is not indexed".
- `db.py` — `sources.image_count INTEGER` (nullable) in SCHEMA, and
  `migrate_db()` ALTER-adds it for legacy DBs (SPEC §4.5 pattern).
- `ui/chat_view.py` — A20 (option 1): when no model is configured, the chat
  `st.chat_input` and task buttons are DISABLED (not hidden); the existing
  "No AI model is configured" warning is the single explanation and no send can
  fail with `Unknown model_id None`.
- `tests/test_image_count.py` (5) — A26/A27: PDF/DOCX counting, floor/never-
  raises, migration adds the column, and the Owner note renders in Manage.

**Modified**
- `tests/test_provider_config_app.py` — no-env tests now blank ALL OPENAI_* vars
  (a real `.env` on disk used to leak into AppTest since it runs with cwd=repo);
  added disabled assertions for the A20 block.
- `SPEC.md` — §15 added (image visibility + no-model send block), acceptance
  criteria A26–A28 added to §10 (no renumbering).
- `memory.md` — OCR scoped-and-deferred (reasons recorded); image count is a
  floor.

**Schema and migration changes**
- `sources` gains `image_count INTEGER` (nullable). `migrate_db()` adds it to
  legacy DBs. No other schema change.

**Acceptance criteria satisfied**
- A26, A27, A28. (A20's send block tightened.) All prior criteria still green.

**Known-broken / deferred**
- OCR is out of scope (memory.md). Image count is a floor, not exact. The A20
  block only hides/disables sends; it does not itself validate config.

---

## 2026-09-11 — Post-Step-7 follow-ups (acceptance matrix completeness)

No build-order step; corrections/tightening after the final sign-off.

**Added**
- `test_multi_workspace.py::test_a3_instructions_and_tasks_do_not_leak` — a
  REAL behavioural test for A3 (was the matrix's weakest "by construction"
  entry): create Workspace B with its own Instructions + a Task, switch to B,
  assert B's task row shows only B's Task (A's `/summarize-policy`/
  `/find-procedure` absent), and that `_load_workspace(B)` carries B's
  instructions (not A's). 55 → 56 passed.
- `ACCEPTANCE_MATRIX.md` — A3 row now points at that test (removed from the
  not-verifiable list); A18/A19 added as an explicit process table.

**Modified**
- `memory.md` — discovery entry recording that OPEN-13 was missing only from my
  owner summary, not from SPEC §11 or the Decision log.

**Schema and migration changes**
- None.

**Known-broken / deferred**
- Step 8 only, as before.

---

## 2026-09-11 — Step 7 — Cleanup (§7.6, §7.7, §7.8)

The final implementable build-order step. Everything an agent can finish without
the project owner is now done.

**Modified**
- `ui/chat_view.py` — §7.6 (option a, the only behavioural change): a free-text
  send while a Task is selected clears the Task selection and, on the next
  render, shows an inline note that the Task was not applied — the message is
  persisted untagged (task_id NULL), so the user isn't misled by a still-lit
  Task chip. Composes with the §7.1 pending-error flow (both fire together).
- `ingestion/pipeline.py` — §7.7: explicit comment at `delete_source()` that
  `chunks_fts` (external-content FTS5) rows MUST be deleted before `chunks`
  rows, with the reason and a guard for future bulk/Workspace deletes.
- `models/context_budget.py` — §7.8: `WORDS_TO_TOKENS` and `estimate_tokens`
  defined here once.
- `ingestion/chunking.py` — §7.8: imports both from `context_budget` and
  re-exports for back-compat. Its fractional per-paragraph accumulation is
  UNCHANGED (no per-paragraph int rounding — that would shift chunk boundaries).
- `ui/pills.py` — §7.8: `ROLE_PILL_MAP` moved here (the natural leaf home);
  no new imports pulled into it.
- `app.py`, `ui/owner_view.py` — import `ROLE_PILL_MAP` from `ui.pills`.
- `.streamlit/config.toml` — §7.8: removed the `static/fonts/README.md`
  reference (chose removal over creating the file, per owner).
- `ui/owner_view.py` — §7.8: raw `sources.error_message` displayed to Owners is
  now prefixed with "Indexing failed — "; the two `st.success`-then-`rerun`
  toasts are replaced by a `wa_owner_toast` session flag rendered after the
  rerun in `render_owner_view`.

**§7.8 "already done" items (not redone)**
- Brittle alignment hack (the `margin-top: 1.6rem` model-note) — done in Step 2b.
- `models/registry.py` docstring pointing at `ui/model_picker.py` — the
  reference was already gone after the Step 2b registry rewrite; only
  `state.md`/`SPEC.md` still mention it (as the defect record).

**Tests added**
- `tests/test_chunking_and_prompt.py::test_chunk_boundaries_unchanged_after_dedupe`
  (§7.8) — pins the exact chunk boundary layout against a reference
  implementation, so the estimate_tokens de-dupe can't silently shift
  boundaries (the ±60 tolerance in the existing test might not catch it).
- `tests/test_task_vs_freetext.py` (3, §7.6) — free-text during an active task
  clears + notes; no task → no note; and the §7.6 × §7.1 interaction (failing
  model still persists the user message, clears the task, shows both the note
  and the retry bubble).

**Schema and migration changes**
- None.

**Acceptance criteria satisfied**
- A18/A19 continue to hold (journal maintained). No new A-numbers; §7.6/7.7/7.8
  are defect fixes.

**Known-broken / deferred**
- Step 8 only — needs real documents + live endpoint (owner inputs). The
  `offline_retrieval_eval.py` CLI-arg change (§9.3) is itself part of Step 8.

---

## 2026-09-11 — Step 6 — Visibility (§5.2.4 grounding + §7.5 model attribution)

**Modified**
- `ui/chat_view.py`:
  - `_grounding_summary(workspace_id)` — single count query returning (indexed,
    failed) for the Workspace. INDEXED sources only (Step-6 item 2): counting
    all rows would tell a Member the Workspace has knowledge when every
    ingestion failed.
  - Grounding status in the chat header for ALL users (§5.2.4): 0 indexed →
    visible warning (A17); >0 → neutral caption "N sources indexed"; failed
    Sources → Owners only, a note pointing at Manage → Knowledge.
  - `_model_display_name(model_id)` + history renderer shows "Model: …" on
    assistant messages (§7.5). Falls back to the raw `model_id` when
    `get_model_spec` raises ValueError — since Step 2b a model can vanish from
    the picker just by blanking a `.env` slug, while historical rows keep that
    id; showing the raw id preserves provenance (Step-6 item 1).

**Added**
- `tests/test_grounding_and_attribution.py` (5 tests) — run AS A MEMBER to
  catch the Member-path-renders-nothing failure mode (Step-6 item 3): A17 (0
  indexed → Member sees the warning), indexed-count caption shown to a Member,
  failed-notes Owner-only (Member still sees the count), §7.5 display-name
  attribution, and unknown-id → raw-id fallback.

**Schema and migration changes**
- None.

**Acceptance criteria satisfied**
- A17. (A15 already covered §7.3's degrade note; attribution is §7.5.)

**Known-broken / deferred**
- Deferred decision from Step 2 (degrade persistence) is now RESOLVED: degraded
  answers are NOT persisted with a marker; reasons in `memory.md` (agent
  decision, owner delegated). The visible per-turn note is the scope.

---

## 2026-09-11 — Step 5 — Multi-Workspace (SPEC.md §5)

Multiple Workspaces per Owner, as specified in §3.1 (the data model already
assumed it; only app.py and the eval harness referenced the constant).

**Modified**
- `app.py` — Workspace switcher in the sidebar (below the user selectbox, above
  navigation): lists the current user's Workspaces via the §5.3 `workspace_members`
  join, ordered by name, persisted in `wa_workspace_id`. `_resolve_workspace()`
  defaults to the first visible on startup / when the stored id is no longer
  visible to the current user (re-evaluates on user switch, §5.2.1). Switching
  clears the old Workspace's `selected_task_{old}` and `wa_chat_id`, then reruns.
  Owner-only "+ New Workspace" expander (§5.2.2: Name required, Instructions
  optional; empty names rejected inline). Branding fix (§5.2.3): page_title is the
  product-level `APP_TITLE` constant; `render_brand()` is called with the current
  Workspace's name — nothing Workspace-specific hardcoded in page chrome (A6).
  Routes the two views with the resolved `workspace_id`.
- `config.py` — `APP_TITLE = "AI Workspace"`; `create_workspace(name, instructions,
  owner)` inserts the Workspace + a `workspace_members` row per EVERY TEST_USER
  (OPEN-4 interim, §5.3); `DEFAULT_WORKSPACE_ID` comment updated (§5.1).

**Added**
- `tests/test_workspace_isolation.py` — A2 at the retrieval layer: two Workspaces,
  each with Sources/chunks/FTS/embeddings; asserts `lexical_search`,
  `semantic_search`, and `hybrid_search` for Workspace A return nothing from
  Workspace B, covering the two independent filters separately (embedding model
  stubbed with a deterministic zero-vector — no HF download).
- `tests/test_multi_workspace.py` — AppTest: A1 (Owner creates a Workspace, it
  appears and is selected, membership = all TEST_USERS), A4 (Workspace switch
  clears selected task + active chat), A5 (Member sees only their Workspaces and
  no Manage button), A6 (branding shows the current Workspace name).
- `tests/conftest.py` — session-scoped assertion that no `data/` directory exists
  at the repo root after the suite runs (mechanical guard for AppTest cwd
  isolation).

**Schema and migration changes**
- None. `workspaces` and `workspace_members` already supported this.

**Acceptance criteria satisfied**
- A1, A2, A4, A5, A6. All prior criteria still green.

**Known-broken / deferred**
- OPEN-5: duplicate Workspace names not rejected (only empty names are). OPEN-6/8
  (Workspace/Chat rename+delete) not built — out of scope until decided.
- The switcher uses a generation counter in the selectbox key so a newly created
  Workspace is actually selected on the next render (avoids the widget retaining a
  stale value); noted so Step 7's cleanup doesn't "simplify" it into the double-answer
  trap (§5.2.1 + Step-5 item 2).

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

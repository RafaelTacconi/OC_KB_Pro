# Acceptance matrix — A1–A25

Verified 2026-09-11 against `68dcd3a` + follow-ups (all of Steps 1–7 complete;
Step 8 not started). Method: each criterion is mapped to the test(s) that prove
it, or is marked *not verifiable* with the reason. The full suite (56 passed)
runs from a clean clone: `git clone` → fresh venv →
`pip install -r requirements.txt` → `python -m pytest tests/ -q` → **56 passed**.

## Multi-Workspace (SPEC §5)

| # | Criterion | Proof | Status |
|---|---|---|---|
| A1 | Owner creates a Workspace; it appears in the switcher and is selected | `tests/test_multi_workspace.py::test_a1_owner_creates_workspace_and_it_is_selected` (AppTest: create → appears + selected; membership = all TEST_USERS) | ✅ |
| A2 | Uploading to Workspace A never retrieved in B | `tests/test_workspace_isolation.py` — retrieval layer, lexical + semantic + hybrid each asserted to return nothing across the boundary (embedder stubbed; verifies the `workspace_id` filter, not ranking) | ✅ |
| A3 | Instructions/Tasks in A don't appear/apply in B | `tests/test_multi_workspace.py::test_a3_instructions_and_tasks_do_not_leak` (AppTest: create Workspace B, give it its own Instructions + Task, verify Workspace A's chat still shows A's Instructions applied and only A's Tasks; and vice-versa) | ✅ |
| A4 | Switching Workspace clears Task + active Chat | `tests/test_multi_workspace.py::test_a4_switch_clears_task_and_active_chat` | ✅ |
| A5 | Member sees only their Workspaces; never reaches Manage | `tests/test_multi_workspace.py::test_a5_member_sees_only_their_workspaces_and_no_manage` | ✅ |
| A6 | Sidebar branding shows current Workspace name; nothing hardcoded | `tests/test_multi_workspace.py::test_a6_branding_uses_workspace_name` + code inspection (page_title = `APP_TITLE`) | ✅ |

## Multi-Chat (SPEC §6)

| # | Criterion | Proof | Status |
|---|---|---|---|
| A7 | New Chat opens empty; previous Chats intact & retrievable | `tests/test_multi_chat.py::test_new_chat_lazy_creation_and_message_routing` | ✅ |
| A8 | Messages appear only in their Chat | same test (routing assertions) | ✅ |
| A9 | Chats scoped per user | `tests/test_multi_chat.py::test_user_scoping_and_workspace_scoping` + `test_wa_chat_id_does_not_leak_across_user_switch` | ✅ |
| A10 | migrate_db() assigns each message to one Chat per (ws, user); no NULL; idempotent | `tests/test_migrate_db.py::test_migrate_db_backfills_legacy_messages`, `test_migrate_db_idempotent`, `test_migrate_db_on_fresh_db_is_noop` (legacy-schema fixture, 2 users × 2 workspaces) | ✅ |
| A11 | Chat lists scoped to current Workspace | `test_user_scoping_and_workspace_scoping` (asserts the chat row's workspace_id); structural (the old `(ws,user)` query removed) | ✅ |

## Reliability (SPEC §7)

| # | Criterion | Proof | Status |
|---|---|---|---|
| A12 | Failed turn → inline error, page alive, user msg persisted after rerun | `tests/test_chat_error_handling.py` | ✅ *see caveat* |
| A13 | Retry = one more attempt, no duplicate user msg | `tests/test_chat_error_handling.py` (counts model attempts) | ✅ *see caveat* |
| A14 | build_prompt includes both small chunks, excludes oversized | `tests/test_spec_v3_regressions.py::test_oversized_chunk_does_not_discard_smaller_relevant_chunks` | ✅ |
| A15 | Embedding model unavailable → lexical-only + visible note | `tests/test_hybrid_search_degrade.py` (3: degrade+signal, clean merge, lexical failure propagates) + UI note in chat_view | ✅ |
| A16 | Source/Task delete needs explicit 2nd confirmation | `tests/test_delete_confirmations.py` (AppTest, arm→cancel→confirm for both) | ✅ |
| A17 | 0 indexed Sources → Member sees visible warning | `tests/test_grounding_and_attribution.py::test_a17_member_sees_warning_when_zero_indexed` (run AS a member) | ✅ |

**⚠ A12/A13 caveat (flagged):** both are proven against a **monkeypatched
`call_model` that raises `RuntimeError("forced model failure…")`** — never against
a real provider failure (timeout, rate-limit, auth). The §7.1 handler is
exercise-true, but the real-failure surface (e.g. `openai.APIError` shapes,
timeouts mid-stream) is unverified until a live `.env` endpoint exists.

## Deployment, credentials, key expiry (SPEC §14 — Addendum A)

| # | Criterion | Proof | Status |
|---|---|---|---|
| A20 | No `.env` → app starts, Manage works, chat shows "no model configured" (incl. partial config) | `tests/test_provider_config_app.py::test_a20_no_env_no_stack_trace_and_no_model_message`, `test_a20_partial_config_missing_key_or_base_url` | ✅ |
| A21 | Blank slug → model omitted; default missing → falls back without raising | `test_a21_picker_filters_and_falls_back_to_first_configured` + `tests/test_provider_config.py::test_list_models_*` | ✅ |
| A22 | Expiry 10d out → Owner sees orange warning on Chat+Manage; nothing blocked | `tests/test_provider_config_app.py::test_a22_expiring_warning_owner_only` | ✅ |
| A23 | 30d → none; past → everyone red; unset/malformed → `unknown` no raise | `tests/test_provider_config.py::test_status_*` (ok/expiring/zero/expired/boundary/unknown/never-raises) | ✅ |
| A24 | `.env` git-ignored; `.env.example` committed; no key/base URL in history | Verified: `git log --all --full-history -- .env` → empty; full-object scan → only `.env.example` ever committed (empty template) | ✅ |
| A25 | `call_model()` signature unchanged; `test_chat_error_handling.py` still passes | Both hold (test monkeypatches `ui.chat_view.call_model` and still passes) | ✅ |

## Not verifiable without owner inputs

- **Live answer quality** — no real endpoint, no real documents. The chat loop
  is real up to the model call (proven), but a grounded answer has never been
  produced.
- **Step 8 / §3.2 hypothesis** — whether focused Workspaces beat a mixed one
  cannot be measured at all until corpora exist.
- **OPEN-2's open half** — the real `context_window_tokens` per model must be
  confirmed against the live endpoint; 256k is still the assumption.

## Process (A18/A19)

| # | Criterion | Proof | Status |
|---|---|---|---|
| A18 | `memory.md`/`state.md`/`changelog.md` exist at repo root and are current | Inspection: every step's entry present in each; `state.md` names the current step + a concrete next action; `changelog.md` has an entry per completed step | ✅ |
| A19 | No `[OPEN]` recorded as resolved on agent authority | `memory.md` Decision log: every `[OPEN]` entry uses one of the three permitted Authority values; the two agent-decided items (Steps 3+4 landing, degrade-persistence) are recorded as owner-delegated, not owner-answered | ✅ |
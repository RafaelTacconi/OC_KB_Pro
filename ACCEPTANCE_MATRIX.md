# Acceptance matrix — A1–A54

Verified 2026-09-14 against current `main` (Steps 1–7 complete, §14/§15/§16 work;
Step 8 run; §7.14/A36, §18/A37–A41, and the spec-only §19/A42–A47 and §20/A48–A54
passes). Method: each criterion is mapped to the test(s) that prove it, or is
marked *not verifiable* / *specified, not built* with the reason. The full suite
(**79 passed**) runs from a clean clone: `git clone` → fresh venv →
`pip install -r requirements.txt` → `python -m pytest tests/ -q`.

## Multi-Workspace (SPEC §5)

| # | Criterion | Proof | Status |
|---|---|---|---|
| A1 | Owner creates a Workspace; it appears in the switcher and is selected | `tests/test_multi_workspace.py::test_a1_owner_creates_workspace_and_it_is_selected` (AppTest: create → appears + selected; membership = creator only per OPEN-4 build) | ✅ |
| A2 | Uploading to Workspace A never retrieved in B | `tests/test_workspace_isolation.py` — retrieval layer, lexical + semantic + hybrid each asserted to return nothing across the boundary (embedder stubbed; verifies the `workspace_id` filter, not ranking) | ✅ |
| A3 | Instructions/Tasks in A don't appear/apply in B | `tests/test_multi_workspace.py::test_a3_instructions_and_tasks_do_not_leak` (AppTest: create Workspace B, give it its own Instructions + Task, verify Workspace A's chat still shows A's Instructions applied and only A's Tasks; and vice-versa) | ✅ |
| A4 | Switching Workspace clears Task + active Chat | `tests/test_multi_workspace.py::test_a4_switch_clears_task_and_active_chat` | ✅ |
| A5 | Member sees only their Workspaces; never reaches Manage | `tests/test_multi_workspace.py::test_a5_member_sees_only_their_workspaces_and_no_manage` | ✅ **Superseded by:** the "never reaches Manage" half is superseded post-PoC by SPEC.md §10's A5 amendment and §17 F10; the "sees only their Workspaces" half survives. Still true and proven today. |
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

## Parsing, citations, answer rendering (SPEC §7.10–§7.13)

| # | Criterion | Proof | Status |
|---|---|---|---|
| A29 | Headings classified by SHAPE, not element type; body fragments never become section titles | `tests/test_parser_headings.py` (5: numbered→heading, fragments rejected, grouping, DOCX real titles) | ✅ *see caveat* |
| A30 | Chip row labelled "Retrieved from" (retrieved set, not the model's citations) | `tests/test_citations_timestamps_export.py::test_a30_chip_row_is_labelled_retrieved_from` | ✅ |
| A31 | Chips deduped by `(display_name, section_title)` | `tests/test_citations_timestamps_export.py::test_a31_chips_dedupe_by_name_and_section` | ✅ |
| A32 | Answer renders on send (inline render; spinner becomes the answer) | `tests/test_citations_timestamps_export.py::test_a32_send_renders_answer` + code inspection of `_answer` (spinner inside the assistant bubble) | ✅ |

**⚠ A29 caveat (updated 2026-09-15):** validated against a real bank procedure on
2026-09-15 — properly styled Word headings produced the correct section title in
every citation, so the caveat is **partially discharged** for Word headings. It
remains **unvalidated for PDFs with sentence-style or unnumbered headings** (see
`memory.md`).

## Message timestamps and chat export (SPEC §16)

| # | Criterion | Proof | Status |
|---|---|---|---|
| A33 | Every message shows a timestamp; stored UTC, displayed local; no schema change | `tests/test_citations_timestamps_export.py::test_a33_format_local_time_converts_from_utc`, `test_a33_and_a34_seeded_chat_shows_timestamp_and_export` | ✅ |
| A34 | Markdown export of the active Chat: question, answer, sources, model, timestamp | `tests/test_citations_timestamps_export.py::test_a34_chat_to_markdown_contains_all_fields`, `test_a33_and_a34_seeded_chat_shows_timestamp_and_export` | ✅ |

## Evaluation (SPEC §9.3)

| # | Criterion | Proof | Status |
|---|---|---|---|
| A35 | Offline harness takes a second CLI arg (`aml`/`hr`/`sec`/`all`) selecting the question set; scoring, `TOP_K`, `retrieval/` unchanged | `tests/offline_retrieval_eval.py` (arg parsing + `AML_QUESTIONS`/`HR_QUESTIONS`/`SEC_QUESTIONS`); run recorded in `changelog.md` (focused 15/15 vs mixed 14/15) | ✅ |

## New-chat selection (SPEC §7.14)

| # | Criterion | Proof | Status |
|---|---|---|---|
| A36 | After the first question in a new Chat: chat stays selected, title updates, Q&A stay on screen without refresh; manual switching and "+ New chat" still work | `tests/test_multi_chat.py::test_a36_new_chat_keeps_selection_after_first_question` (AppTest; seeds a prior chat so the sentinel selector renders, then sends the new chat's first question) | ✅ |

## Grounding rules in the system prompt (SPEC §18) — hand-run only

These are **not** automatically tested (no automated test may call the live
model). They are verified by the owner re-running the seven-case regression set
in `GROUNDING_REGRESSION.md`.

| # | Criterion | Proof | Status |
|---|---|---|---|
| A37 | A stated gap is stopped at — nothing is added after "the documents do not say" (no general knowledge, no "typically", no textbook definition, no plausible inference) | `GROUNDING_REGRESSION.md` G4, G5 (hand-run) + code inspection of `prompting/assemble.py::SYSTEM_POLICY` rule 1 | ✅ *hand-run only* |
| A38 | No date, duration, or elapsed time calculated/inferred from a value the documents do not contain | `GROUNDING_REGRESSION.md` G2, G6 (hand-run) + `SYSTEM_POLICY` rule 2 | ✅ *hand-run only* |
| A39 | Document silence never presented as a rule — "not stated" is not "continuous"/"always"/"never"/"no exception" | `GROUNDING_REGRESSION.md` G3, G6 (hand-run) + `SYSTEM_POLICY` rule 3 | ✅ *hand-run only* |
| A40 | Two sources called agreeing/disagreeing only when BOTH address the subject; when only one does, say so | `GROUNDING_REGRESSION.md` G7 (hand-run) + `SYSTEM_POLICY` rule 4 | ✅ *hand-run only* |
| A41 | A multi-answer question gets all answers, labelled, or a request to clarify — never one picked silently | `GROUNDING_REGRESSION.md` G1 (hand-run) + `SYSTEM_POLICY` rule 5 | ✅ *hand-run only* |

## Activity logging (SPEC §19) — specified 2026-09-14, NOT built

All rows below are specification only. There is no logging code; proof is the
specified behaviour in `SPEC.md` §19.

| # | Criterion | Proof | Status |
|---|---|---|---|
| A42 | Logs in their own SQLite DB; main DB gains no log table; log DB holds no KB/chat/config/membership rows; a logging burst cannot block a question; log DB never in a KB backup | `SPEC.md` §19.1 | *specified, not built* |
| A43 | Knowledge base, chats, Workspace config, and membership stay in the one DB separated by `workspace_id`; Workspace delete remains a single atomic action | `SPEC.md` §19.1 | *specified, not built* |
| A44 | Tier 1 always on, exactly the listed metadata fields, never question/answer text, non-sensitive, retained freely | `SPEC.md` §19.2 | *specified, not built* |
| A45 | Tier 2 off by default, enabled per Workspace by its Owner, stores Q/A + chunk ids only while on, UI states plainly what is stored | `SPEC.md` §19.2 | *specified, not built* |
| A46 | Refusal rate computable from Tier 1 (`workspace_id`, timestamp, `outcome` ∈ answered/refused/error), sliceable per Workspace over time | `SPEC.md` §19.3 | *specified, not built* |
| A47 | Log storage is the DB alone (no per-session files); retention/deletion independent of the KB DB | `SPEC.md` §19.4 | *specified, not built* |

## Service interface / API (SPEC §20) — specified 2026-09-14, NOT built

All rows below are specification only. No endpoint exists; proof is the specified
behaviour in `SPEC.md` §20.

| # | Criterion | Proof | Status |
|---|---|---|---|
| A48 | Division of responsibility stated (service vs calling task/workflow system) | `SPEC.md` §20.1 | *specified, not built* |
| A49 | Request identifies Workspace (`workspace_id`, not name), question, optional model; malformed → documented `400` | `SPEC.md` §20.2, §20.6 | *specified, not built* |
| A50 | Response returns answer + structured `sources` (document/section/page where supported); no `grounded` flag; empty `sources` is the interim signal | `SPEC.md` §20.3 | *specified, not built* |
| A51 | Caller identified by API credential mapped to Workspace membership; API not built/exposed until OPEN-13/OPEN-14 resolved; C6 no-auth is UI-only | `SPEC.md` §20.4 | *specified, not built* |
| A52 | Empty retrieval → documented refusal + `sources: []`, nothing fabricated | `SPEC.md` §20.5 | *specified, not built* |
| A53 | Distinct documented status/code for bad Workspace, unknown caller, provider failure, oversized request, no model, malformed request; no stack traces | `SPEC.md` §20.6 | *specified, not built* |
| A54 | Rate limiting required and per-caller (shared provider key + SQLite single writer); limit value is a deployment parameter | `SPEC.md` §20.7 | *specified, not built* |

## Not verifiable without owner inputs

- **Live answer quality** — no live endpoint in this runtime. The owner's
  hand-run 2026-09-13 evaluation reached a live model on their machine (15/15,
  recorded in `changelog.md`), and the hand-run adversarial suite surfaced the
  seven grounding failures now covered by A37–A41; those need a re-run to confirm
  the prompt fix.
- **Step 8 / §3.2 hypothesis** — RUN 2026-09-13 on the re-uploaded corpus:
  focused 15/15 vs mixed 14/15 (essentially flat). Recorded in `changelog.md` and
  `state.md`; the owner decides what (if anything) it changes. No retrieval
  parameter was changed.
- **OPEN-2's open half** — the real `context_window_tokens` per model must be
  confirmed against the live endpoint; 256k is still the assumption.

## Process (A18/A19)

| # | Criterion | Proof | Status |
|---|---|---|---|
| A18 | `memory.md`/`state.md`/`changelog.md` exist at repo root and are current | Inspection: every step's entry present in each; `state.md` names the current step + a concrete next action; `changelog.md` has an entry per completed step | ✅ |
| A19 | No `[OPEN]` recorded as resolved on agent authority | `memory.md` Decision log: every `[OPEN]` entry uses one of the three permitted Authority values; the two agent-decided items (Steps 3+4 landing, degrade-persistence) are recorded as owner-delegated, not owner-answered | ✅ |
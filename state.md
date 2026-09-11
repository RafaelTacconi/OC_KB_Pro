# state.md — where the work is right now

Overwritten in place on every update. Keep under one page. Rules: `SPEC.md` §13.3.
History belongs in `changelog.md`, not here.

**Last updated:** 2026-09-11 — Step 1 started.

---

## Current step

**Step 1 — unblock the app (in progress).** Fix §7.2 (`break` → `continue` in
`prompting/assemble.py`) and §7.1 (error handling + message persistence in
`ui/chat_view.py::_answer()`). Both are self-contained defect fixes.

## Progress

| Step | Description | Status |
|---|---|---|
| 1 | Unblock the app — fix §7.2 (`break` → `continue` + test) and §7.1 (error handling, message persistence) | In progress |
| 2 | Resilience — §7.3 lexical degrade path, §7.4 delete confirmations | Not started |
| 3 | Schema — `chats` table, `chat_messages.chat_id`, indexes, `migrate_db()` | Not started |
| 4 | Multi-Chat — history by `chat_id`, new chat, chat selector, titling | Not started |
| 5 | Multi-Workspace — selector, create form, membership, branding fix | Not started |
| 6 | Visibility — grounding status, model attribution in history | Not started |
| 7 | Cleanup — §7.6, §7.7, §7.8 | Not started |
| 8 | Evaluate — §9.3 offline retrieval evaluation | Not started (needs real documents) |

## Blocked on

Nothing blocks Step 1: §7.1 and §7.2 depend on no `[OPEN]` item.

Note: §7.1's "create the `chats` row here too if the Chat is new (§6.2)" is
deferred to Step 4 — the `chats` table does not exist until Step 3's schema
migration. Noted under deviations in `memory.md`.

## Test status

Baseline before any edit:

```
python -m pytest tests/ -q
1 failed, 7 passed
```
`tests/test_spec_v3_regressions.py::test_oversized_chunk_does_not_discard_smaller_relevant_chunks`
fails on purpose (A14). It must pass when Step 1 finishes.
Test-suite rerun pending after edits — see changelog/commit.

## Next action

In `prompting/assemble.py`, change `break` to `continue` in the retrieved-chunk
loop (line ~52), then run `python -m pytest tests/ -q` and confirm **8 passed**.
Then implement §7.1 in `ui/chat_view.py::_answer()`: persist the user message
first, split the turn into a Streamlit-free `_run_turn()`, wrap in try/except,
stash the failure in `st.session_state["wa_pending_error"]`, render an inline
assistant error bubble with a Retry button after history, and verify A12/A13
headlessly via `streamlit.testing.v1.AppTest`.
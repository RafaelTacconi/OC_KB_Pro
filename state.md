# state.md — where the work is right now

Overwritten in place on every update. Keep under one page. Rules: `SPEC.md` §13.3.
History belongs in `changelog.md`, not here.

**Last updated:** 2026-09-11 — Step 1 complete.

---

## Current step

**Step 2 — resilience (next).** Fix §7.3 (lexical degrade path in
`retrieval/hybrid_search.py::hybrid_search()`) and §7.4 (delete confirmations in
`ui/owner_view.py`). Both are self-contained defect fixes that depend on no
`[OPEN]` item.

## Progress

| Step | Description | Status |
|---|---|---|
| 1 | Unblock the app — fix §7.2 (`break` → `continue` + test) and §7.1 (error handling, message persistence) | **Done** |
| 2 | Resilience — §7.3 lexical degrade path, §7.4 delete confirmations | Not started |
| 3 | Schema — `chats` table, `chat_messages.chat_id`, indexes, `migrate_db()` | Not started |
| 4 | Multi-Chat — history by `chat_id`, new chat, chat selector, titling | Not started |
| 5 | Multi-Workspace — selector, create form, membership, branding fix | Not started |
| 6 | Visibility — grounding status, model attribution in history | Not started |
| 7 | Cleanup — §7.6, §7.7, §7.8 | Not started |
| 8 | Evaluate — §9.3 offline retrieval evaluation | Not started (needs real documents) |

## Blocked on

Nothing blocks Step 2.

Pre-existing note (open since Step 1): §7.1's "create the `chats` row here too
if the Chat is new" is deferred to Step 4 — the `chats` table does not exist
until Step 3. See `memory.md` deviations.

**OPEN-3** (does chat history enter the prompt?) blocks nothing before Step 4,
but answering it early would avoid rework: the interim build is Option A, and
switching to Option B afterwards touches `build_prompt()`, the token budget,
and possibly the retrieval query.

## Test status

```
python -m pytest tests/ -q
9 passed in 9.09s
```
Run on 2026-09-11 after completing Step 1 (previously 7 passed, 1 failed —
the intentional A14 failure is now green, and `tests/test_chat_error_handling.py`
added A12/A13 coverage).

## Next action

Start Step 2. In `retrieval/hybrid_search.py::hybrid_search()`, wrap the
`semantic_search()` call in `try/except Exception`; on failure return lexical
results only and signal degradation without importing Streamlit — the §7.3
specified signal is "communicate it through a return value or a documented
exception-free signal", so plan a return-shape change (the remaining spec
detail to settle: whether `_answer` and `_run_turn` in `ui/chat_view.py` expect
the new shape — read `hybrid_search` callers before choosing). Then add the
§7.4 two-step confirm in `ui/owner_view.py` for Source and Task deletion with a
session-state flag keyed by entity id. Run `python -m pytest tests/ -q` before
and after.
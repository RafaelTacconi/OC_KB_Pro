# state.md — where the work is right now

Overwritten in place on every update. Keep under one page. Rules: `SPEC.md` §13.3.
History belongs in `changelog.md`, not here.

**Last updated:** 2026-09-11 — Step 5 complete.

---

## Current step

**Step 6 — visibility (next).** Grounding status for all users (§5.2.4: a count query →
warning when 0 indexed Sources / neutral caption when >0 / failed-Sources note for Owners) and
model attribution in history (§7.5: show `model_id`'s display_name as a caption/pill on
assistant messages, handling unknown ids gracefully). Also consider the §7.3 degrade-persistence
note recorded in `memory.md` (whether to persist a marker for degraded answers).

## Progress

| Step | Description | Status |
|---|---|---|
| 1 | Unblock the app — fix §7.2 (`break` → `continue` + test) and §7.1 (error handling, message persistence) | **Done** |
| 2 | Resilience — §7.3 lexical degrade path, §7.4 delete confirmations | **Done** |
| 2b | Provider config and key expiry — §14: `.env`, adapter, `models/credentials.py`, sidebar warning | **Done** |
| 3+4 | Schema + multi-Chat (landed together) | **Done** |
| 5 | Multi-Workspace — selector, create form, membership, branding fix | **Done** |
| 6 | Visibility — grounding status, model attribution in history | Not started |
| 7 | Cleanup — §7.6, §7.7, §7.8 | Not started — **§7.8 "brittle alignment hack" already done in Step 2b** (the `margin-top: 1.6rem` in `ui/chat_view.py` model-note was removed when that line was touched — do not redo or skip around it) |
| 8 | Evaluate — §9.3 offline retrieval evaluation | Not started (needs real documents) |

## Blocked on

Nothing blocks Step 6. It has no `[OPEN]` dependency.

**OPEN-3/4/5/7 interim applied** (`memory.md`). **OPEN-2** updated not closed.
**OPEN-12** interim implemented. **OPEN-11** answered (OpenAI-compatible proxy).

## Test status

```
python -m pytest tests/ -q
46 passed in 17.36s
```
Run on 2026-09-11 after Step 5. Added `tests/test_workspace_isolation.py` (A2 at
the retrieval layer, lexical + semantic separately, 3 tests) and
`tests/test_multi_workspace.py` (A1/A4/A5/A6 AppTest, 4 tests). The suite now
also asserts no `data/` at the repo root after every run (`tests/conftest.py`).

## Next action

Start Step 6. In `ui/chat_view.py`, add a one-line grounding status in the chat
header for ALL users derived from a single `SELECT COUNT(*) FROM sources WHERE
workspace_id = ? AND status='indexed'` (0 → warning that answers won't be
grounded; >0 → neutral caption "N sources indexed"; any failed source → Owners
only, a note pointing at Manage → Knowledge) using `ui/pills.py`/`ui/cards.py`.
Then §7.5: in the history renderer, for assistant messages with non-null
`model_id`, render `models.registry.get_model_spec(model_id).display_name` as a
small caption/pill alongside the citation chips, wrapped so an unknown id raises
no error (historical rows can outlive registry entries). Consider the
degrade-persistence decision in `memory.md`. Run `python -m pytest tests/ -q`
before and after.
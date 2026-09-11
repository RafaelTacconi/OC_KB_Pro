# state.md — where the work is right now

Overwritten in place on every update. Keep under one page. Rules: `SPEC.md` §13.3.
History belongs in `changelog.md`, not here.

**Last updated:** 2026-09-11 — Step 2 complete.

---

## Current step

**Step 3 — schema (next).** Add `chats` table (SPEC §4.2), `chat_messages.chat_id`
(§4.3), the five indexes (§4.4), write `db.migrate_db()` and wire it into
`config.bootstrap()` immediately after `init_db()` (§4.5). Verify against both a
fresh DB and a copy of an existing one; `migrate_db()` must be idempotent (run
twice = no change) and backfill `chat_messages.chat_id` per distinct
`(workspace_id, user_id)` with one `chats` row titled "Imported conversation".

## Progress

| Step | Description | Status |
|---|---|---|
| 1 | Unblock the app — fix §7.2 (`break` → `continue` + test) and §7.1 (error handling, message persistence) | **Done** |
| 2 | Resilience — §7.3 lexical degrade path, §7.4 delete confirmations | **Done** |
| 3 | Schema — `chats` table, `chat_messages.chat_id`, indexes, `migrate_db()` | Not started |
| 4 | Multi-Chat — history by `chat_id`, new chat, chat selector, titling | Not started |
| 5 | Multi-Workspace — selector, create form, membership, branding fix | Not started |
| 6 | Visibility — grounding status, model attribution in history | Not started |
| 7 | Cleanup — §7.6, §7.7, §7.8 | Not started |
| 8 | Evaluate — §9.3 offline retrieval evaluation | Not started (needs real documents) |

## Blocked on

Nothing blocks Step 3. It has no `[OPEN]` dependency.

Pre-existing note: §7.1's "create the `chats` row here too if the Chat is new"
is deferred to Step 4 — Step 3 creates the `chats` table and the migration, so
Step 4 can implement it. See `memory.md` deviations.

**OPEN-3** (does chat history enter the prompt?) blocks nothing before Step 4,
but answering it early would avoid rework: the interim build is Option A, and
switching to Option B afterwards touches `build_prompt()`, the token budget,
and possibly the retrieval query.

## Test status

```
python -m pytest tests/ -q
14 passed in 14.66s
```
Run on 2026-09-11 after completing Step 2. Added:
`tests/test_hybrid_search_degrade.py` (§7.3, 3 tests) and
`tests/test_delete_confirmations.py` (A16, 2 tests). Previous Steps' suites
still green. No `data/` is ever written into the repository root — all AppTest
tests run in a temp cwd.

## Next action

Start Step 3. In `db.py` add the `chats` table to `SCHEMA`, add
`chat_messages.chat_id TEXT REFERENCES chats(chat_id)`, add the five indexes
from SPEC §4.4, and write `migrate_db()` performing the §4.5 steps (check
`PRAGMA table_info(chat_messages)` for `chat_id`, ALTER if absent, backfill one
`chats` row per distinct `(workspace_id, user_id)` with `chat_id IS NULL`, then
create the indexes). Wire `migrate_db()` into `config.bootstrap()` right after
`init_db()`. Verify: fresh empty DB, a DB with legacy messages (backfill
creates "Imported conversation" chats and no row ends up `chat_id IS NULL`,
per A10), and running it twice changes nothing. Run `python -m pytest tests/ -q`
before and after.
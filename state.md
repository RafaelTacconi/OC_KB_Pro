# state.md — where the work is right now

Overwritten in place on every update. Keep under one page. Rules: `SPEC.md` §13.3.
History belongs in `changelog.md`, not here.

**Last updated:** 2026-09-11 — Step 2b + follow-ups done; Step 3/4 next.

---

## Current step

**Steps 3 + 4 — to be landed TOGETHER in one commit (decision recorded 2026-09-11).**
Step 3: add `chats` table (SPEC §4.2), `chat_messages.chat_id` (§4.3), the five
indexes (§4.4), write `db.migrate_db()` and wire it into `config.bootstrap()`
immediately after `init_db()` (§4.5). Step 4: `_load_history(chat_id)`,
`chat_id` through `_save_message`, `+ New chat`, Chat selector, lazy creation
and titling, Option A prompt behaviour (§6.5).

**Why together:** splitting leaves `_save_message()` writing `chat_id = NULL`
between commits — the exact state A10 forbids (with only the next `migrate_db()`
self-healing it). Landing migration + the Chat features that use `chat_id`
atomically means no NULL-chat_id window ever exists. See memory.md
"Steps 3+4 landed together".

## Progress

| Step | Description | Status |
|---|---|---|
| 1 | Unblock the app — fix §7.2 (`break` → `continue` + test) and §7.1 (error handling, message persistence) | **Done** |
| 2 | Resilience — §7.3 lexical degrade path, §7.4 delete confirmations | **Done** |
| 2b | Provider config and key expiry — §14: `.env`, adapter, `models/credentials.py`, sidebar warning | **Done** |
| 3 + 4 | Schema + multi-Chat (landed together) | Not started |
| 5 | Multi-Workspace — selector, create form, membership, branding fix | Not started |
| 6 | Visibility — grounding status, model attribution in history | Not started |
| 7 | Cleanup — §7.6, §7.7, §7.8 | Not started — **§7.8 "brittle alignment hack" already done in Step 2b** (the `margin-top: 1.6rem` in `ui/chat_view.py` model-note was removed when that line was touched — do not redo or skip around it) |
| 8 | Evaluate — §9.3 offline retrieval evaluation | Not started (needs real documents) |

## Blocked on

Nothing blocks Steps 3+4. No `[OPEN]` dependency.

**OPEN-11** is **answered** (2026-09-11) — OpenAI-compatible proxy, `openai`
SDK, not Azure; logged in `memory.md`. **OPEN-12** interim behaviour
implemented. **OPEN-2** updated, not closed. **OPEN-3** (does chat history
enter the prompt?) is the one to answer early: the interim build is Option A
(no history in prompt); switching to Option B afterwards touches
`build_prompt()`, the token budget, and possibly the retrieval query.

Pre-existing note: §7.1's "create the `chats` row here too if the Chat is new"
is implemented as part of Step 4 (landing with Step 3), per §6.2 lazy creation.

## Test status

```
python -m pytest tests/ -q
32 passed in 13.19s
```
Run on 2026-09-11 after the Step 2b partial-config follow-up. Breakdown:
Step 2 ended at 14; Step 2b added 16 (test_provider_config.py: 13 unit,
test_provider_config_app.py: 3 AppTest) → 30; this follow-up added 2
(partial-config unit + AppTest A20 extension) → 32.

## Next action

Build Steps 3+4 as one commit. In `db.py`: add `chats` table (§4.2),
`chat_messages.chat_id` (§4.3), the five indexes (§4.4), and `migrate_db()`
(§4.5: check `PRAGMA table_info(chat_messages)` for `chat_id`, ALTER if absent,
backfill one `chats` row per distinct `(workspace_id, user_id)` with
`chat_id IS NULL` titled "Imported conversation", create indexes). Wire
`migrate_db()` into `config.bootstrap()` after `init_db()`. Then Step 4 in
`ui/chat_view.py`: `_load_history(chat_id)` (drop the old two-arg query),
`_save_message(chat_id=...)` at every write, `+ New chat` (lazy), Chat selector
ordered by `updated_at`, titling from first message. Verify: fresh DB + legacy
DB (A10: no row `chat_id IS NULL`, idempotent twice), A7/A8/A9/A11, and
`python -m pytest tests/ -q` before and after.
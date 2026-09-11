# state.md — where the work is right now

Overwritten in place on every update. Keep under one page. Rules: `SPEC.md` §13.3.
History belongs in `changelog.md`, not here.

**Last updated:** 2026-09-11 — Steps 3+4 complete.

---

## Current step

**Step 5 — multi-Workspace (next).** Workspace selector + create form (Owner only,
§5.2.2), membership rule (§5.3, interim: all TEST_USERS), branding fix (§5.2.3:
`page_title` / `render_brand` use `APP_TITLE` + current Workspace name, nothing
hardcoded in `app.py`), state resets on switch. The Workspace list for a user is
derived from `workspace_members` (the §5.3 join query), never from `workspaces`
directly.

## Progress

| Step | Description | Status |
|---|---|---|
| 1 | Unblock the app — fix §7.2 (`break` → `continue` + test) and §7.1 (error handling, message persistence) | **Done** |
| 2 | Resilience — §7.3 lexical degrade path, §7.4 delete confirmations | **Done** |
| 2b | Provider config and key expiry — §14: `.env`, adapter, `models/credentials.py`, sidebar warning | **Done** |
| 3+4 | Schema + multi-Chat (landed together) | **Done** |
| 5 | Multi-Workspace — selector, create form, membership, branding fix | Not started |
| 6 | Visibility — grounding status, model attribution in history | Not started |
| 7 | Cleanup — §7.6, §7.7, §7.8 | Not started — **§7.8 "brittle alignment hack" already done in Step 2b** (the `margin-top: 1.6rem` in `ui/chat_view.py` model-note was removed when that line was touched — do not redo or skip around it) |
| 8 | Evaluate — §9.3 offline retrieval evaluation | Not started (needs real documents) |

## Blocked on

Nothing blocks Step 5. It has no `[OPEN]` dependency.

**OPEN-4** (who is a member of a newly created Workspace) has an interim — add all
TEST_USERS; do not invent a private-Workspace mechanism. **OPEN-5** (name
uniqueness) is not enforced — reject only empty/whitespace names. **OPEN-6/8**
(rename/delete Workspace/Chat) not built. **OPEN-3 interim applied** (Option A);
**OPEN-7 interim applied** (first-message titling); both Authority: Agent applied
spec interim (`memory.md`).

## Test status

```
python -m pytest tests/ -q
38 passed in 14.58s
```
Run on 2026-09-11 after Steps 3+4. Added `tests/test_migrate_db.py` (3, A10) and
`tests/test_multi_chat.py` (3, A7-A9/A11 + §6.5 caption). All prior suites green.

## Next action

Start Step 5. In `app.py`: add a Workspace selector below the user selectbox
(listing the current user's Workspaces via `workspace_members` join, ordered by
name), persist in `st.session_state["wa_workspace_id"]`, default to the first on
startup / when the stored id is no longer visible to the current user. Add the
Owner-only "+ New Workspace" expander (Name required, Instructions optional;
insert `workspaces` row + `workspace_members` row per every TEST_USER, §5.3
interim, then set `wa_workspace_id` to the new id + rerun). Fix branding: define
`APP_TITLE = "AI Workspace"` in `config.py`, use it for `st.set_page_config`'s
`page_title` and `render_brand(workspace_name, "AI Workspace")`. On Workspace
switch, clear `selected_task_{old}` and `wa_chat_id`. Run
`python -m pytest tests/ -q` before and after.
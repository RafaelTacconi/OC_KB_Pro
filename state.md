# state.md — where the work is right now

Overwritten in place on every update. Keep under one page. Rules: `SPEC.md` §13.3.
History belongs in `changelog.md`, not here.

**Last updated:** 2026-09-11 — Addendum A merged; Step 2b next.

---

## Current step

**Step 2b — Provider configuration and key expiry.** New build-order step inserted
between Steps 2 and 3 by Addendum A (merged into `SPEC.md` §14). `.env.example`,
`.gitignore` entry, `python-dotenv`, lazy environment reads, registry/env split,
OpenAI-compatible adapter replacing the placeholder, `models/credentials.py`,
sidebar warning. **OPEN-11 must be answered by the project owner before the
adapter is written** — the user has confirmed they will answer it.

## Progress

| Step | Description | Status |
|---|---|---|
| 1 | Unblock the app — fix §7.2 (`break` → `continue` + test) and §7.1 (error handling, message persistence) | **Done** |
| 2 | Resilience — §7.3 lexical degrade path, §7.4 delete confirmations | **Done** |
| 2b | Provider config and key expiry — §14: `.env`, adapter, `models/credentials.py`, sidebar warning | Not started |
| 3 | Schema — `chats` table, `chat_messages.chat_id`, indexes, `migrate_db()` | Not started |
| 4 | Multi-Chat — history by `chat_id`, new chat, chat selector, titling | Not started |
| 5 | Multi-Workspace — selector, create form, membership, branding fix | Not started |
| 6 | Visibility — grounding status, model attribution in history | Not started |
| 7 | Cleanup — §7.6, §7.7, §7.8 | Not started |
| 8 | Evaluate — §9.3 offline retrieval evaluation | Not started (needs real documents) |

## Blocked on

**OPEN-11** (which OpenAI-compatible client: proxy / Azure / direct) blocks the
router adapter at the start of Step 2b. The owner is answering it now. Everything
else in Step 2b (`.env.example`, `.gitignore`, `python-dotenv`, lazy reads,
registry/env split, `credentials.py`, sidebar warning) does not depend on it.

**OPEN-12** (who sees the pre-expiry warning) has an interim behaviour — implement
it, do not block. **OPEN-2** is updated, not closed (signature confirmed; context
windows still need the real endpoint).

Speaking only `OPEN-3` forward: nothing further blocks until Step 4.

## Test status

```
python -m pytest tests/ -q
14 passed in 14.66s
```
Run on 2026-09-11 after completing Step 2. Step 2b is unbuilt so no suite change yet.

## Next action

Start Step 2b, in this order: (1) add `.env.example` (committed) and the `.env`
`.gitignore` entry; (2) add `python-dotenv` to `requirements.txt` and call
`load_dotenv()` at the top of `config.py`; (3) remove the module-scope
`INTERNAL_API_KEY = os.environ.get(...)` from `models/router.py` so every env read
is lazy inside the function; (4) registry/env split in `models/registry.py` +
picker fallback; (5) `models/credentials.py::api_key_status()` + sidebar warning;
(6) **the OpenAI-compatible adapter — WAIT for the owner's OPEN-11 answer first.**
Run `python -m pytest tests/ -q` before and after; A25 must stay green.
# state.md — where the work is right now

Overwritten in place on every update. Keep under one page. Rules: `SPEC.md` §13.3.
This copy is written for a **human operator** (the project owner) — all build-order
steps an implementing agent can complete are done; what remains needs you.

**Last updated:** 2026-09-11 — Steps 1–7 + §15 complete; Step 8 awaiting owner inputs.

---

## Where the project stands

**Implemented and green (Steps 1–7 + SPEC §15).** The full test suite passes from a
clean clone: `git clone` → fresh venv → `pip install -r requirements.txt` →
`python -m pytest tests/ -q` → **61 passed**. Acceptance matrix for A1–A25 is in
`ACCEPTANCE_MATRIX.md`. §15 added A26–A28 (embedded-image visibility + no-model
send block). What has never been exercised: a **live model call** and **real
documents**. A `.env` is configured in this repo (OpenRouter-compatible endpoint
with 2 model slugs), so the app boots with a working model picker, but no real
document has been ingested and no live model answer has been produced.

## Blocked on

**OPEN-11 is answered** (OpenAI-compatible proxy, `openai` SDK). **OPEN-12, 3, 4,
5, 7** have interim behaviour applied (`memory.md` Decision log, Authority: Agent
applied spec interim). **OPEN-2** is updated-not-closed (context windows still
256k assumption). What blocks nothing else: Step 8 needs documents + endpoint.

## Step 8 — what you need to supply, run, and interpret

Two things must exist before anything here works: a configured `.env` and real
documents. Nothing in this section is runnable without them.

### 0. Configure the model endpoint
1. `git clone git@github.com:RafaelTacconi/OC_KB_Pro.git`
2. `cd OC_KB_Pro && python -m venv .venv && .venv\Scripts\pip install -r requirements.txt`
3. `copy .env.example .env` and fill in:
   - `OPENAI_BASE_URL=` — the OpenAI-compatible proxy URL
   - `OPENAI_API_KEY=` — the key
   - `OPENAI_MODEL_FAST=` / `OPENAI_MODEL_STANDARD=` / `OPENAI_MODEL_REASONING=`
     — the exact slugs the endpoint expects. **Leave a slug blank to hide that
     model from the picker.** Blank a slug to confirm OPEN-2's context-window
     numbers later.
   - `OPENAI_API_KEY_EXPIRES_ON=` — `YYYY-MM-DD`, optional; a 14-day countdown
     warning shows to Owners only, `expired` shows red to everyone.
4. `streamlit run app.py` — sign in as **Alex (Owner)**.

A send should now return a live answer. If it fails: the §7.1 inline error with
the exception in the expander tells you why (auth, timeout, model slug …). If the
error says "not recognized"/"deployment not found"-style, STOP — that indicates
Azure, which is not supported (OPEN-11); the adapter is OpenAI-compatible only.

### 1. Upload real documents per Workspace
Manage → Knowledge → upload your pdf/docx/xlsx per Workspace and hit
*Process uploaded files*. Confirm each shows **indexed**. (The first upload
downloads `all-MiniLM-L6-v2` — needs outbound network to huggingface.co at least
once.)

### 2. Ground-truth question sets (Step 8 task — the code change is NOT yet made)
`tests/offline_retrieval_eval.py` currently **hardcodes `DEFAULT_WORKSPACE_ID`**
and has an empty `QUESTION_SET`. §9.3 required turning the constant into a CLI
argument. **This change is part of Step 8 and has not been made.** If you want
the per-Workspace comparison, apply it first:

- edit `if __name__ == "__main__":` in `tests/offline_retrieval_eval.py` to read
  `sys.argv[1]` as the workspace_id instead of importing the constant.
- fill `QUESTION_SET` with 10–15 questions per topic, each with
  `expected_source_substring` = a distinctive part of the source file's
  display_name.

### 3. Run the §3.2 focus-hypothesis protocol
1. One **mixed** Workspace containing all documents from all topics.
2. Three **focused** Workspaces, each containing only its topic's documents.
3. Run the harness against each: `python -m tests.offline_retrieval_eval <ws_id>`.
4. Compare top-5 hit rates per question set.

**What the results mean** (SPEC §9.3):

| Result | Conclusion |
|---|---|
| Focused runs clearly beat mixed | Segregation helps retrieval; keep it. |
| Focused ≈ mixed | The benefit of segregation is the Instructions/Tasks effect (§3.2a), not retrieval; still a real reason to segregate. |
| Focused < mixed | Unexpected; capture the output and reconsider. |

Also while you have a live endpoint: confirm each model's real
`context_window_tokens` (OPEN-2) and correct `models/registry.py` if 256k is
wrong — `fits_in_context()` uses it.

## Progress

| Step | Status |
|---|---|
| 1 — Unblock app (7.2 break→continue, 7.1 error handling/persistence) | Done |
| 2 — Resilience (7.3 lexical degrade, 7.4 delete confirms) | Done |
| 2b — Provider config & key expiry (`.env`, adapter, credentials.py) | Done |
| 3+4 — Schema (chats) + multi-Chat, landed together | Done |
| 5 — Multi-Workspace (switch, create, branding, membership) | Done |
| 6 — Visibility (grounding status, model attribution) | Done |
| 7 — Cleanup (7.6, 7.7, 7.8) | Done |
| §15 — Image visibility + no-model send block | Done |
| 8 — Evaluate (§9.3) | **Not started — needs your documents + live model call** |

## Test status

```
python -m pytest tests/ -q
61 passed in 35.86s   (2026-09-11)
```
Verified from a **clean clone** earlier (fresh venv, fresh install): 55 passed at
`a9d033c`; the later A3/§15 additions brought it to 61. No `data/` is ever written
into the repo root by the suite (conftest guard). NOTE: the suite must run from a
cwd with no `.env` (tests blank the model vars themselves), so a stray `data/`
from a manually-launched app must be removed before `pytest` or the conftest
guard trips.

## Next action

For the owner: complete the Step 8 inputs (documents per Workspace, ground-truth
question sets, the `offline_retrieval_eval.py` CLI-arg change), then run the §3.2
protocol. `.env` is configured (2 model slugs), so the chat loop can be exercised
now. Before test users: use the §15.1 Manage → Knowledge image note to size how
much of the image-heavy corpus is image-only and unindexed (the earlier
`scripts/image_audit.py` idea was superseded by the in-app warning). There is no
implementation work left that an agent can do without you.
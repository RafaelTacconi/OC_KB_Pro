# state.md — where the work is right now

Overwritten in place on every update. Keep under one page. Rules: `SPEC.md` §13.3.
This copy is written for a **human operator** (the project owner) — all build-order
steps an implementing agent can complete are done; what remains needs you.

**Last updated:** 2026-09-13 — Steps 1–7 + §14/§15/§16 done, §17 stub added, OPEN-14 raised; Step 8 awaiting owner inputs.

---

## Where the project stands

**Implemented and green (Steps 1–7 + SPEC §14/§15/§16).** The full suite passes
from a clean clone: `python -m pytest tests/ -q` → **78 passed**. Acceptance
matrix for **A1–A34** is in `ACCEPTANCE_MATRIX.md`. Recent additions: §15
embedded-image visibility + no-model send block (A26–A28); the post-test fixes
§7.10–§7.13 (A29–A32, incl. the shape-based heading fix); §16 message timestamps
+ Markdown chat export (A33–A34). §17 is a titles-only stub for post-PoC
direction (F1–F11).

What has **never** been exercised: a **live model call** and **real documents**
in the current runtime. A `.env` is configured (OpenRouter-compatible endpoint,
2 model slugs), so the app boots with a working model picker.

**Runtime `data/` is EMPTY** (only an app-bootstrapped `workspace_app.db`; no
sources, no conversations). The corpus must be **re-uploaded** — via a terminal
with the venv active — before Step 8 or the adversarial suite can run.

## Blocked on

Step 8 needs: (1) the corpus re-uploaded per Workspace, (2) ground-truth
questions in `tests/offline_retrieval_eval.py`, (3) a live model call.

**OPEN-14** (new): is the port already network-restricted? Owner is confirming
with IT; do not answer. **OPEN-13** is deferred to the deployment layer.
**OPEN-11** answered (OpenAI-compatible proxy). **OPEN-12/3/4/5/7** interim
applied. **OPEN-4 is closed** (per-Workspace membership built). **OPEN-2** is
updated-not-closed (context windows still 256k assumption).

## Step 8 — what you need to supply, run, and interpret

### 0. Model endpoint
`.env` is already configured in this repo (base URL + key + 2 model slugs). On a
fresh clone: `copy .env.example .env` and fill in `OPENAI_BASE_URL`,
`OPENAI_API_KEY`, and the `OPENAI_MODEL_*` slugs. `streamlit run app.py` runs
**from a terminal with `.venv` activated** — the embedder (`sentence-transformers`)
must be present in the serving interpreter or uploads fail.

> **DEPLOYMENT WARNING (OPEN-13):** no authentication. Anyone who can reach the
> Streamlit port can select "Alex (Owner)" and delete any Workspace. Per-Workspace
> membership gates *visibility*, not *identity*. **Put a network/reverse-proxy
> auth layer in front of the port before exposing it.** OPEN-14 asks whether
> that restriction already exists — unverified.

### 1. Re-upload real documents per Workspace
Manage → Knowledge → upload pdf/docx/xlsx per Workspace → *Process uploaded
files* → confirm **indexed**. (First upload downloads `all-MiniLM-L6-v2` once.)

### 2. Ground-truth questions (the CLI-arg change is DONE)
`tests/offline_retrieval_eval.py` now takes the workspace_id as a CLI argument
(§9.3). Only `QUESTION_SET` is empty — fill it with 10–15 questions per topic,
each with `expected_source_substring`, then run:
`python -m tests.offline_retrieval_eval <workspace_id>`.

### 3. Run the §3.2 focus-hypothesis protocol
Mixed Workspace vs three focused Workspaces; compare top-5 hit rates.

| Result | Conclusion |
|---|---|
| Focused beats mixed | Segregation helps retrieval. |
| Focused ≈ mixed | Benefit is the Instructions/Tasks effect (§3.2a), not retrieval. |
| Focused < mixed | Unexpected; capture and reconsider. |

While you have a live endpoint: confirm each model's real `context_window_tokens`
(OPEN-2) and correct `models/registry.py` if 256k is wrong.

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
| §16 — Message timestamps + Markdown chat export | Done |
| §17 — Post-PoC direction (titles-only stub) | Documented, not built (by direction) |
| 8 — Evaluate (§9.3) | **Not started — needs corpus re-upload + live model call** |

## Test status

```
python -m pytest tests/ -q
78 passed   (2026-09-13)
```
The conftest `data/` guard is snapshot-based: a pre-existing `data/` from a
stopped app is tolerated; the suite fails only if the TESTS create/modify/delete
repo `data/`. Run the suite with the app **stopped**.

## Next action

For the owner: re-upload the corpus (terminal with venv active), fill
`QUESTION_SET` in `tests/offline_retrieval_eval.py`, then run
`python -m tests.offline_retrieval_eval <workspace_id>` and the §3.2 protocol.
There is no implementation work left that an agent can do without you.
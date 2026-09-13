# state.md — where the work is right now

Overwritten in place on every update. Keep under one page. Rules: `SPEC.md` §13.3.
This copy is written for a **human operator** (the project owner) — all build-order
steps an implementing agent can complete are done; what remains needs you.

**Last updated:** 2026-09-13 — Steps 1–7 + §14/§15/§16 done; **Step 8 focused-vs-mixed evaluation RUN** (results recorded); decision pending.

---

## Where the project stands

**Implemented and green (Steps 1–7 + SPEC §14/§15/§16).** The full suite passes
from a clean clone: `python -m pytest tests/ -q` → **78 passed**. Acceptance
matrix for **A1–A34** is in `ACCEPTANCE_MATRIX.md`. Recent additions: §15
embedded-image visibility + no-model send block (A26–A28); the post-test fixes
§7.10–§7.13 (A29–A32, incl. the shape-based heading fix); §16 message timestamps
+ Markdown chat export (A33–A34); §9.3 second CLI argument (A35). §17 is a
titles-only stub for post-PoC direction (F1–F11).

**Step 8 focused-vs-mixed evaluation RAN (2026-09-13),** on the re-uploaded
corpus (four Workspaces, all docs indexed). Top-5 hit rate (hybrid):

| Run | Set | Hit rate |
|---|---|---|
| AML workspace | AML (6) | 6/6 = 100% |
| HR workspace | HR (4) | 4/4 = 100% |
| ITSEC workspace | SEC (5) | 5/5 = 100% |
| All Policies (mixed) | all (15) | 14/15 = 93% |

Focused 15/15 vs mixed 14/15 — a single-question difference (**essentially
flat**). The one mixed miss: *"Who has the final say on telling the regulator
about a breach?"* (expected `Incident_Response_Procedure.docx`; it passed in the
focused ITSEC run). Interpretation per §9.3: the benefit of segregation appears
to be the Instructions/Tasks effect (§3.2a), not retrieval. **No retrieval
parameter was changed** — the owner decides next. Full detail in `changelog.md`.

`data/` now holds the corpus (3+3+3+9 docs across four Workspaces). Do not clear
it. A live model call has still not been exercised end-to-end in this runtime.

## Blocked on

Step 8's numbers are recorded; the **next decision is the owner's** (whether the
result changes anything — it does not motivate a retrieval-parameter change).

**OPEN-14**: is the port already network-restricted? Owner is confirming with IT;
do not answer. **OPEN-13** deferred to the deployment layer. **OPEN-11** answered
(OpenAI-compatible proxy). **OPEN-12/3/4/5/7** interim applied. **OPEN-4 closed**
(per-Workspace membership built). **OPEN-2** updated-not-closed (context windows
still 256k assumption).

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

### 2. Ground-truth questions (DONE — run it any time)
`tests/offline_retrieval_eval.py` takes **two** CLI arguments now: the
workspace_id and a question set (`aml` / `hr` / `sec` / `all`). The three lists
are populated. Run:
`python -m tests.offline_retrieval_eval <workspace_id> <aml|hr|sec|all>`.

### 3. §3.2 focus-hypothesis protocol — RUN 2026-09-13
Result: focused 15/15 (100%) vs mixed 14/15 (93%) — a single-question difference
(essentially flat). Reading: the benefit of segregation is the Instructions/Tasks
effect (§3.2a), not retrieval. No retrieval parameter changed; the owner decides.

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
| 8 — Evaluate (§9.3) | **RUN (2026-09-13) — results recorded; owner decision pending** |

## Test status

```
python -m pytest tests/ -q
78 passed   (2026-09-13)
```
The conftest `data/` guard is snapshot-based: a pre-existing `data/` from a
stopped app is tolerated; the suite fails only if the TESTS create/modify/delete
repo `data/`. Run the suite with the app **stopped**.

## Next action

For the owner: **decide what (if anything) the flat §3.2 result changes** — the
numbers do not motivate changing `top_k`/`MAX_RETRIEVED_TOKENS`/`rrf_k`/
`candidate_pool`/chunk size, and no such change has been made. Remaining
independent tasks: run the hand-checked negative control in chat; the adversarial
suite (`adversarial_tests.md`, owner-run); confirm context windows against the
live endpoint (OPEN-2). There is no implementation work left that an agent can do
without you.
# state.md — where the work is right now

Overwritten in place on every update. Keep under one page. Rules: `SPEC.md` §13.3.
This copy is written for a **human operator** (the project owner) — all build-order
steps an implementing agent can complete are done; what remains needs you.

**Last updated:** 2026-09-14 — Steps 1–7 + §14/§15/§16 + §7.14/§18 done; Step 8 RUN (results recorded); spec-only §19/§20/§21 added (nothing built); **README rewritten around the service purpose; matrix retitled A1–A54**; owner review pending.

---

## Where the project stands

**Implemented and green (Steps 1–7 + SPEC §14/§15/§16 + §7.14/§18).** The full
suite passes from a clean clone: `python -m pytest tests/ -q` → **79 passed**.
Acceptance matrix for **A1–A41** is in `ACCEPTANCE_MATRIX.md`. Recent additions:
§15 embedded-image visibility + no-model send block (A26–A28); the post-test
fixes §7.10–§7.14 (A29–A32, A36, incl. shape-based headings and the new-chat
selection fix); §16 message timestamps + Markdown chat export (A33–A34); §9.3
second CLI argument (A35); §18 grounding rules in `SYSTEM_POLICY` (A37–A41,
prompt-level only, hand-verified via `GROUNDING_REGRESSION.md`). §17 is a
titles-only stub for post-PoC direction (F1–F11).

**Newly specified, NOT built (spec-only pass 2026-09-14):** §19 Activity logging
(F4), §20 Service interface / API (F7), §21 build sequencing, and criteria
A42–A54. Review these in `SPEC.md` before any implementation. The chosen order is
§19 first, §20 second, monitoring dashboard last (unspecified until real log data
exists).

**README.md** now explains the tool for a first-time reader: what it is (refusal
is the point), how it works, its scope vs the calling system, honest status, known
limitations, and the launch warning. `ACCEPTANCE_MATRIX.md` covers A1–A54.

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
still 256k assumption; now blocks §20). **OPEN-15/16/17** newly recorded
(API `grounded` flag; retrieval under pasted case context; chat retention) — none
answered; none blocks building §19.

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
| §7.14 — New-chat selection after first question (A36) | Done |
| §18 — Grounding rules in the system prompt (A37–A41) | Done (prompt-level only; hand-verified) |
| §19 — Activity logging (A42–A47) | **Specified (2026-09-14), not built** |
| §20 — Service interface / API (A48–A54) | **Specified (2026-09-14), not built** |
| §21 — Build sequencing (logging → API → dashboard) | **Recorded (2026-09-14); no criteria** |
| §17 — Post-PoC direction (titles-only stub) | Documented, not built (by direction) |
| 8 — Evaluate (§9.3) | **RUN (2026-09-13) — results recorded; owner decision pending** |

## Test status

```
python -m pytest tests/ -q
79 passed   (2026-09-14, docs-only pass)
```
Known flake (see memory.md): `test_chat_error_handling.py::test_failed_turn_persists_question_and_retry_does_not_duplicate`
failed once under a slow (68s) run, passes in isolation; suspected timeout, not
diagnosed.
The conftest `data/` guard is snapshot-based: a pre-existing `data/` from a
stopped app is tolerated; the suite fails only if the TESTS create/modify/delete
repo `data/`. Run the suite with the app **stopped**.

## Next action

For the owner: **read and correct `SPEC.md` §19 / §20 / §21** before any build.
Nothing there is implemented. Once approved, the build order is fixed: **§19
activity logging first** (a service must be measurable before it is exposed),
then §20 API, then — much later and only after real log data exists — a
monitoring dashboard. Independent remaining tasks unchanged: re-run the
seven-case grounding regression set (`GROUNDING_REGRESSION.md`, needs a live
endpoint) to confirm A37–A41; confirm context windows against the live endpoint
(OPEN-2, now blocking §20); decide what the flat §3.2 result changes.
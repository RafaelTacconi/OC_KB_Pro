# state.md — where the work is right now

Overwritten in place on every update. Keep under one page. Rules: `SPEC.md` §13.3.
This copy is written for a **human operator** (the project owner) — all build-order
steps an implementing agent can complete are done; what remains needs you.

**Last updated:** 2026-09-15 — Steps 1–7 + §14/§15/§16 + §7.14/§18 done; Step 8 RUN; **Tier 1 logging + localhost-only staging API BUILT (SPEC §19.6/§20.9-§20.13, A55–A62)**; first real-document validation done (A29 partially discharged); xlsx row-count defect deferred by direction.

---

## Where the project stands

**Implemented and green (Steps 1–7 + SPEC §14/§15/§16 + §7.14/§18 + §19.6/§20.9–§20.13).** The full
suite passes from a clean clone: `python -m pytest tests/ -q` → **93 passed**. Acceptance matrix for
**A1–A54** is in `ACCEPTANCE_MATRIX.md` (A55–A62 not yet added there). Recent additions: §15
embedded-image visibility + no-model send block (A26–A28); the post-test fixes §7.10–§7.14
(A29–A32, A36); §16 message timestamps + Markdown chat export (A33–A34); §9.3 second CLI argument
(A35); §18 grounding rules (A37–A41); **§19.6 Tier 1 logging (A55); §20.9–§20.13 localhost-only
staging API (A56–A62)**. §17 is a titles-only stub (F1–F11).

**Newly built, staging scope only (2026-09-15):** **Tier 1 logging** (`activity_log.py`, separate
`data/logs.db`, WAL + `busy_timeout`; main DB unchanged) and the **staging API** (`service/`, reuse
of `retrieval/`/`prompting/`/`models/`, loopback-only, static `KB_API_KEY`). **Not built:** Tier 2,
rate limiting, per-caller identity, production auth. See `memory.md`.

**Still specified-only:** the production §20 surface (A48–A54), the monitoring dashboard (§21).

**README.md** explains the tool for a first-time reader. `ACCEPTANCE_MATRIX.md` covers A1–A54 (the
new A55–A62 are not yet added there).

**First real-document validation (2026-09-15):** a real bank procedure — four
documents (2 .docx with 23 tables/9 images, 1 .xlsx with 7 sheets, 1 .pdf), 19
questions. A29's heading heuristic produced correct section titles in every
citation (partial discharge of the caveat). Grounding held on all five
adversarial-style questions. Three image-only questions were correctly refused.
**One real defect found:** xlsx row counting is wrong when a sheet has a title
block — the model stated "45 rows" for a 42-row sheet. Root cause investigated
(`parsers.py::parse_xlsx`, `header=0`); **fix proposed, NOT built, owner approval
pending** (see `memory.md`). An ingestion fix means re-processing xlsx Sources.

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
| §19 — Tier 1 activity logging (A42–A47, A55) | **Tier 1 BUILT (2026-09-15); Tier 2 not built** |
| §20 — Service interface / API | **Staging subset BUILT, localhost-only (A56–A62); production surface (A48–A54) not built** |
| §21 — Build sequencing (logging → API → dashboard) | **Recorded (2026-09-14); no criteria** |
| §17 — Post-PoC direction (titles-only stub) | Documented, not built (by direction) |
| xlsx row-count defect (ingestion) | **Deferred by direction 2026-09-15 (build not approved)** |
| 8 — Evaluate (§9.3) | **RUN (2026-09-13) — results recorded; owner decision pending** |

## Test status

```
python -m pytest tests/ -q
93 passed   (2026-09-15)
```
Known flake (see memory.md): `test_chat_error_handling.py::test_failed_turn_persists_question_and_retry_does_not_duplicate`
failed once under a slow (68s) run, passes in isolation; suspected timeout, not
diagnosed.
The conftest `data/` guard is snapshot-based: a pre-existing `data/` from a
stopped app is tolerated; the suite fails only if the TESTS create/modify/delete
repo `data/`. Run the suite with the app **stopped**.

## Next action

**Try the staging API end to end on your machine** (needs a live `.env` model
endpoint): add `KB_API_KEY` to `.env`, then
`python -m service.api` (terminal, venv active), then from a second terminal
`python scripts/measure_open16.py <workspace_id> "your question"` to run the
OPEN-16 three-way retrieval measurement. The API is loopback-only by construction
and refuses to start otherwise; 401/404/503 paths are verified, the **success path
needs your live endpoint** and has not been run here.

Then, for the owner: **`SPEC.md` §19.6 / §20.9–§20.13 / A55–A62** describe what
was built; correct anything you disagree with. **The xlsx row-count fix stays
parked** until it can travel with other ingestion work (owner direction
2026-09-15; see `memory.md`). Independent remaining tasks unchanged: re-run the
seven-case grounding regression set (`GROUNDING_REGRESSION.md`, live endpoint) to
confirm A37–A41; confirm context windows against the live endpoint (OPEN-2);
decide what the flat §3.2 result changes.
# state.md — where the work is right now

Overwritten in place on every update. Keep under one page. Rules: `SPEC.md` §13.3.
History belongs in `changelog.md`, not here.

**Last updated:** 2026-09-11 — Step 7 complete.

---

## Current step

**Step 8 — evaluate (blocked on the project owner).** §9.3 offline retrieval
evaluation via `tests/offline_retrieval_eval.py`. Cannot be started from this
repo: it needs (1) real documents and (2) a live model endpoint (
`OPENAI_BASE_URL` / `OPENAI_API_KEY` / `OPENAI_MODEL_*` in `.env`). Until then,
no further build-order step is implementable.

Everything the spec allows an implementing agent to finish without the owner is
done. Steps 1–7 are complete; all acceptance criteria through A17 (and A18/A19,
journal) are green. The remaining owner inputs: real corpora + per-Workspace
question sets (Step 8), and the still-open `[OPEN]` items (none block Run).

## Progress

| Step | Description | Status |
|---|---|---|
| 1 | Unblock the app — fix §7.2 (`break` → `continue` + test) and §7.1 (error handling, message persistence) | **Done** |
| 2 | Resilience — §7.3 lexical degrade path, §7.4 delete confirmations | **Done** |
| 2b | Provider config and key expiry — §14: `.env`, adapter, `models/credentials.py`, sidebar warning | **Done** |
| 3+4 | Schema + multi-Chat (landed together) | **Done** |
| 5 | Multi-Workspace — selector, create form, membership, branding fix | **Done** |
| 6 | Visibility — grounding status, model attribution in history | **Done** |
| 7 | Cleanup — §7.6, §7.7, §7.8 | **Done** |
| 8 | Evaluate — §9.3 offline retrieval evaluation | Blocked — needs real documents + live endpoint (owner) |

## Blocked on

Step 8 (the only remaining step) needs owner input: real documents uploaded per
Workspace, 10–15 ground-truth questions per topic in `tests/offline_retrieval_eval.py`,
and a live model endpoint in `.env`. Nothing CODE-wise blocks.

**OPEN-3/4/5/7 interim applied** (`memory.md`). **OPEN-2** updated not closed.
**OPEN-12** interim implemented. **OPEN-11** answered (OpenAI-compatible proxy).
Deferred decision resolved: degraded answers are NOT persisted with a marker
(`memory.md`, agent decision 2026-09-11).

## Test status

```
python -m pytest tests/ -q
55 passed in 20.95s
```
Run on 2026-09-11 after Step 7. Added `tests/test_chunking_and_prompt.py::test_chunk_boundaries_unchanged_after_dedupe`
(1, §7.8) and `tests/test_task_vs_freetext.py` (3, §7.6 incl. pending-error
interaction). No `data/` at the repo root after the suite (conftest).

## Next action

Step 7 is done. Hand back to the project owner for Step 8 inputs: (1) copy
`.env.example` to `.env` and fill in `OPENAI_BASE_URL`, `OPENAI_API_KEY`,
`OPENAI_MODEL_*` — the app's chat loop is then real; (2) upload real documents
through Manage → Knowledge per Workspace; (3) write 10–15 questions per topic
with a known ground-truth source into `tests/offline_retrieval_eval.py`
(`QUESTION_SET`), then `python -m tests.offline_retrieval_eval <workspace_id>`
(needs the CLI-arg change from §9.3, not yet made — it is Step 8 itself).
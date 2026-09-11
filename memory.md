# memory.md — decisions, discoveries, and things learned the hard way

Append-only. Never edit or delete a past entry; if one turns out to be wrong, add a new
entry that supersedes it and name the entry it replaces. Format and rules: `SPEC.md` §13.2.

---

## Decision log

Every `[OPEN]` item from `SPEC.md` §11 is pre-listed below as **not yet reached**. When the
agent encounters one, it replaces that item's `Outcome` / `Authority` / `Consequence` lines
with a dated entry — and the `Authority` line may only ever read *Agent applied spec interim*,
*Deferred — not reached*, or *Answered by project owner on `<date>`* (`SPEC.md` §10, A19).

### OPEN-1 — Missing spec v2
Question: Where is the original "Internal AI Workspace Application spec (v2)"? Section
references throughout the code (Sections 4–16, acceptance criteria #1–#10) are unverifiable
without it.
Outcome: Deferred — not reached.
Authority: Deferred — not reached.
Consequence: `SPEC.md` may contradict v2 in ways nobody can currently detect.

### OPEN-2 — `call_model` signature and registry accuracy
Question: Is widening constraint C4 to `call_model(prompt, model_id)` approved? Are the
`provider_model_name` slugs and 256k context figures in `models/registry.py` correct?
Outcome: Deferred — not reached.
Authority: Deferred — not reached.
Consequence: The registry's context-window numbers feed `fits_in_context()`; wrong numbers
mean a wrong guard.

### OPEN-3 — Does chat history enter the prompt?
Question: Do a Chat's prior turns go into the assembled prompt (`SPEC.md` §3.3, §6.5)?
Outcome: Deferred — not reached.
Authority: Deferred — not reached.
Consequence: **The most consequential open item.** Determines whether multiple Chats is a
context-management feature or a UI organisation feature. Option A (interim) keeps the current
stateless behaviour; Option B changes the v2 prompt assembly order.

### OPEN-4 — Membership on a new Workspace
Question: Who is a member of a newly created Workspace (`SPEC.md` §5.3)?
Outcome: Deferred — not reached.
Authority: Deferred — not reached.
Consequence: Under the interim rule (all `TEST_USERS`), an Owner cannot create a private
Workspace.

### OPEN-5 — Name uniqueness
Question: Should Workspace names (and Task names) be unique?
Outcome: Deferred — not reached.
Authority: Deferred — not reached.
Consequence: Duplicate names in a selectbox are indistinguishable to the user.

### OPEN-6 — Workspace rename and delete
Question: Can a Workspace be renamed or deleted? What happens to users currently in it, and
to the last remaining Workspace (`SPEC.md` §5.5)?
Outcome: Deferred — not reached.
Authority: Deferred — not reached.
Consequence: Without delete, an Owner experimenting with segregation accumulates dead
Workspaces and their embeddings.

### OPEN-7 — Chat titling
Question: How is a Chat titled (`SPEC.md` §6.2)?
Outcome: Deferred — not reached.
Authority: Deferred — not reached.
Consequence: A model-generated title costs an extra call; a user-editable title needs UI.

### OPEN-8 — Chat rename and delete
Question: Can a Chat be renamed or deleted?
Outcome: Deferred — not reached.
Authority: Deferred — not reached.
Consequence: Same accumulation problem as OPEN-6, at higher volume.

### OPEN-9 — Accepted limitations
Question: Should any of the accepted limitations in `SPEC.md` §7.9 be addressed for this PoC
(stopword filtering, duplicate Task names, glyph icons, type sizes, responsiveness, caching,
streaming)?
Outcome: Deferred — not reached.
Authority: Deferred — not reached.
Consequence: Several — stopword filtering especially — would change retrieval behaviour and
invalidate any evaluation run performed before the change.

### OPEN-10 — Cross-Workspace search
Question: Is there a cross-Workspace question path — searching several Workspaces at once?
Outcome: Deferred — not reached.
Authority: Deferred — not reached.
Consequence: This is the main functional cost of Workspace segregation (`SPEC.md` §3.1).

---

## Codebase discoveries

Non-obvious facts established by reading or running the code. The three below were verified by
execution while `SPEC.md` was written and are recorded here so they are not rediscovered.

### 2026-09-11 — FTS5 deletion ordering is load-bearing
`chunks_fts` is an external-content FTS5 table (`content='chunks'`). Deleting an index row with
`DELETE FROM chunks_fts WHERE rowid = ?` works **only while the matching `chunks` row still
exists** — FTS5 reads the content row to determine which terms to remove. `delete_source()`
gets this order right today. Any new cascade (Workspace delete, bulk delete) must delete FTS
rows *before* `chunks` rows or it silently corrupts the index. See `SPEC.md` §5.5, §7.7.

### 2026-09-11 — The existing budget test cannot catch the `break` bug
`test_build_prompt_respects_token_budget` uses two chunks of 2600 tokens each. Under both
`break` and `continue` the second chunk is excluded, so the test passes either way. It is not a
regression guard for `SPEC.md` §7.2; `tests/test_spec_v3_regressions.py` is.

### 2026-09-11 — Chat history never reaches the model
`build_prompt()` accepts only `workspace_instructions`, `retrieved_chunks`, `user_input`,
`task_prompt`, `model_id`. Prior turns are stored and rendered but never sent. Every turn is
stateless, so conversation length has no effect on prompt size or context-window usage. This is
what makes OPEN-3 a real decision rather than a formality.

---

## Rejected approaches

*(none yet — record what was tried and why it was abandoned, so it is not re-litigated)*

---

## Deviations from the spec

*(none yet — anything built differently from `SPEC.md`, with the reason. If the spec is wrong
or unimplementable, say so here and in the final report. Do not diverge quietly.)*

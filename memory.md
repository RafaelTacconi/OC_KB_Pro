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

### 2026-09-11 — The app is testable end-to-end via streamlit.testing.v1.AppTest
`AppTest.from_file("app.py").run()` executes the real app headlessly — `st.chat_input`,
`st.error`, `st.button(key=...)` and `st.rerun()` (auto-followed) behave as in a real session.
Relative DB paths resolve against the process cwd, so `monkeypatch.chdir(tmp_path)` gives full
DB isolation. `at.error` exposes `st.error` bubble text. The endpoint stub's
`NotImplementedError` is reached only when `INTERNAL_API_KEY` is set — otherwise
`_call_internal_gateway()` raises `RuntimeError` first — so set it in tests to match A12's
wording. Used by `tests/test_chat_error_handling.py` (Step 1).

### 2026-09-11 — requirements install: unstructured DID install cleanly here
The `unstructured[pdf,docx]>=0.15` extra installed without failure in `.venv` (torch 2.14,
sentence-transformers 6.0.1, streamlit 1.63.0, pytest 9.1.1). The sandbox also has a route to
huggingface.co — `all-MiniLM-L6-v2` downloaded and loaded during the Step 1 A12/A13
verification, so ingestion would not be expected to fail for network reasons here. Both
speculative failure modes (`unstructured` not installing; no HF route) did not apply.

### 2026-09-11 — The `break` bug's required test and the budget test coexist under `continue`
`test_oversized_chunk_does_not_discard_smaller_relevant_chunks` (A14) and
`test_build_prompt_respects_token_budget` both pass under `continue` — the former because the
two small chunks fit the 3000-token budget after the oversized one is skipped, the latter
because its two 2600-token chunks are each too big to coexist. Both were green in the 8-pass
run after the §7.2 one-liner.

### 2026-09-11 — hybrid_search now returns (chunks, degraded), not a list
`§7.3` changed the contract: `retrieval/hybrid_search.py::hybrid_search()` returns
`tuple[list[dict], bool]` where the bool is True when semantic search was unavailable and the
results are lexical-only. Exactly two callers exist and both were updated in Step 2:
`ui/chat_view.py::_run_turn` (surfaces the §7.3 note via `wa_semantic_degraded`) and
`tests/offline_retrieval_eval.py::run_eval`. The eval harness RAISES on degrade rather than
falling back (owner-directed): a silent fallback would make hybrid and lexical-only produce
identical rows and falsely suggest hybrid adds nothing. lexical_search failures are NOT part
of the degrade path and propagate to the §7.1 handler.

---

## Rejected approaches

*(none yet — record what was tried and why it was abandoned, so it is not re-litigated)*

---

## Deviations from the spec

### 2026-09-11 — §7.1 chats-row creation deferred to Step 4
SPEC §7.1 requirement 1 says the user-message persist step should also "create the `chats`
row here too if the Chat is new (§6.2)". The `chats` table does not exist until Step 3's
schema migration (§4.2), and multi-Chat wiring is Step 4. Deferred: in this build the whole
`chats` concept is absent, so there is no row to create. Revisit when Step 4 lands.
**Spec change needed (minor):** none — this is a build-order consequence already signalled by
`state.md`.

### 2026-09-11 — A failed turn leaves a persisted user message with no answer and no retry once the session ends
Retry state lives only in `st.session_state["wa_pending_error"]`, so if the client closes the
tab the turn is permanently user-message-only, with no answer and a retry affordance that is
gone. This is a direct consequence of applying §7.1 exactly (do not persist an assistant
message containing the error, or it would pollute the Chat and, under Option B, the model's
own context). Not changed for Step 1; flagged for the project owner if longer-lived retry
(an assistant placeholder row, or re-running by sending the same text again) is wanted.

### 2026-09-11 — Embedding-model load failures are now remembered for the session
`ingestion/embedding.py::_get_model()` previously only cached a successful load, so every
call after a failure re-attempted the model download. Once §7.3 made `hybrid_search()` catch
instead of crash, every chat turn would have re-attempted it — paying a network/model timeout
per turn. Changed (owner-approved, see decision for Step 1 — point 3): a failed load is stored
in `_model_load_error` and every subsequent call raises fast with a short message pointing at
the root cause; recovering requires an app restart once the model/network works. Logged as a
deviation from the previous behaviour at the owner's request.

---

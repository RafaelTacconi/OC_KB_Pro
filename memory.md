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

### OPEN-2 — `call_model` signature and registry accuracy — 2026-09-11 (supersedes entry above)
Question: Is widening constraint C4 to `call_model(prompt, model_id)` approved? Are the
`provider_model_name` slugs and 256k context figures in `models/registry.py` correct?
Outcome: Signature confirmed — `call_model(prompt, model_id) -> str` stays (§14.4, A25).
Real base URL / key / slugs move to `.env` (§14.3) via a lazy `provider_model_name()`
read in `models/registry.py`. Still open: each model's real `context_window_tokens`.
Authority: Answered by project owner on 2026-09-11 (signature); context windows still
Deferred — not reached.
Consequence: `fits_in_context()` keeps using 256k until the real windows are confirmed.
NOTE: this entry was first written by EDITING the entry above in place (a §13.2 violation),
then restored to append-only form on 2026-09-11. No content was lost.

### OPEN-3 — Does chat history enter the prompt? — 2026-09-11
Question: Do a Chat's prior turns go into the assembled prompt (`SPEC.md` §3.3, §6.5)?
Outcome: **Option A (interim) applied.** Prior turns in a Chat are NOT sent to the model —
`build_prompt()` keeps its current signature and assembly order. A Chat is an organisational
thread only; every turn is answered independently. The chat view shows the §6.5 honesty
caption ("each question is answered independently… does not remember earlier turns").
Authority: Agent applied spec interim. NOT answered by project owner.
Consequence: Switching to Option B (history in the prompt) later touches `build_prompt()`,
its token budget, and possibly the retrieval query — a contained, spec'd delta (§6.5).

### OPEN-4 — Membership on a new Workspace — 2026-09-11
Question: Who is a member of a newly created Workspace (`SPEC.md` §5.3)?
Outcome: **Interim applied.** On Workspace creation (`config.create_workspace`), a
`workspace_members` row is inserted for EVERY entry in `TEST_USERS`, mirroring the seed
behaviour. The Workspace list a user sees is derived from `workspace_members` (§5.3 join),
never from `workspaces` directly, so a rule change needs one place only.
Authority: Agent applied spec interim. NOT answered by project owner.
Consequence: An Owner cannot create a private Workspace. If per-Workspace access control is
wanted, it is a new requirement needing an invite/removal mechanism in Manage → Users
(currently read-only), plus an explicit decision.

### OPEN-5 — Name uniqueness — 2026-09-11
Question: Should Workspace names (and Task names) be unique?
Outcome: **Interim applied.** Uniqueness is NOT enforced — two Workspaces may share a name
(`workspaces.name` has no unique constraint). Only empty/whitespace-only names are rejected
at creation (inline message, no row inserted). This is a known usability hazard with a
name-labelled selectbox.
Authority: Agent applied spec interim. NOT answered by project owner.
Consequence: Duplicate names in the switcher/selectbox are indistinguishable to the user.

### OPEN-6 — Workspace rename and delete
Question: Can a Workspace be renamed or deleted? What happens to users currently in it, and
to the last remaining Workspace (`SPEC.md` §5.5)?
Outcome: Deferred — not reached.
Authority: Deferred — not reached.
Consequence: Without delete, an Owner experimenting with segregation accumulates dead
Workspaces and their embeddings.

### OPEN-7 — Chat titling — 2026-09-11
Question: How is a Chat titled (`SPEC.md` §6.2)?
Outcome: **Interim applied.** On the first user message in a Chat, the title is set to that
message's text truncated to 60 characters (single line, trailing whitespace stripped, `…`
appended if truncated) — `_chat_title_from_message()` in `ui/chat_view.py`. Until a message
arrives (lazy creation) there is no row; the selector shows the empty/new-chat caption.
Authority: Agent applied spec interim. NOT answered by project owner.
Consequence: A model-generated summary title would cost an extra call; a user-editable title
needs UI. Neither is built.

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

### OPEN-11 — Which OpenAI-compatible client? — 2026-09-11
Question: Is the endpoint an OpenAI-compatible proxy, Azure OpenAI, or `api.openai.com`
directly (`SPEC.md` §14.4)?
Outcome: **OpenAI-compatible proxy.** Use the `openai` SDK — `OpenAI(base_url=..., api_key=...)`,
model slug passed as `model`. Owner confirmed it is not Azure, so no Azure guard and no
`OPENAI_API_VERSION` variable. Base URL stays empty in `.env.example`; filled in at config time.
Authority: Answered by project owner on 2026-09-11.
Consequence: Implement §14.4 case 1 exactly. Adapter replaces `_call_internal_gateway()`;
`call_model(prompt, model_id) -> str` signature unchanged (A25).

### OPEN-12 — Who sees the pre-expiry warning?
Question: The brief says "the relevant users" see the pre-expiry key warning (`SPEC.md` §14.5)
— who exactly?
Outcome: Deferred — not reached.
Authority: Deferred — not reached.
Consequence: Interim is `expiring`/`unknown` to Owners; `expired` to all. Members cannot renew
a key, but their chat breaks when it lapses.

### OPEN-13 — Authentication on an internal deployment
Question: The internally deployed app has no authentication — anyone reaching the port can
sign in as Owner and manage/delete any Workspace (`SPEC.md` §14.1). Network-restricted host,
or a gate before deployment?
Outcome: Deferred — not reached.
Authority: Deferred — not reached.
Consequence: Constraint C6 was written for laptop testing; do NOT build authentication in
response to this — flag it and continue.

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

### 2026-09-11 — A degraded answer is persisted identically to a grounded one — note for Step 6
After §7.3, a successful-but-degraded turn persists its assistant message with **no marker**
distinguishing it from a fully-grounded one: the degrade only lives in session state
(`wa_semantic_degraded`, which survives until the next send). There is no column on
`chat_messages` for it, and `cited_sources`/`retrieved_chunk_ids` are the same shape either
way. **Step 6 (visibility) should decide whether to record the degrade on the message** —
e.g. a marker in the message or a `degraded` column — rather than relying on the
session-only note. Not built now; the spec (§7.3) requires only the visible note.

### 2026-09-11 — DECIDED: degraded answers are NOT persisted with a marker — supersedes the note above
Step 6 reached the deferred decision. **Decision: do not record the degrade on the message.**
Reasons: (1) SPEC §7.3 requires only the visible note, and nothing in §5–§6 or the acceptance
criteria requires persistence; (2) persisting it needs either a new `degraded` column on
`chat_messages` (a schema change + migration beyond the spec, touching Step 3's migration
contract) or a marker baked into the assistant content (which would pollute the message text
and, under OPEN-3 Option B, the model's own context); (3) the visible `wa_semantic_degraded`
note already surfaces on the turn where it matters. The current-turn note is the correct
scope. Authority: agent's decision (owner delegated; recorded 2026-09-11). If history-level
review of degraded answers is ever wanted, revisit with a real column.

### 2026-09-11 — openai SDK v3 API surface (Step 2b)
The installed `openai` SDK is v3.x. The adapter path is
`OpenAI(base_url=..., api_key=...)` then `client.chat.completions.create(model=slug, messages=[...])`,
reading `response.choices[0].message.content`. Base URL and key are only read inside the
adapter call (lazy, per §14.2); the "unconfigured" guard raises `RuntimeError` BEFORE the SDK
is imported, so a missing `.env` never triggers a network/import side effect (validated —
the fail-fast happens pre-`openai` import). The SDK does not fetch anything at `OpenAI(...)`
construction; errors surface at the `.create()` call.

### 2026-09-11 — A keyed Streamlit widget retains its value and fights a programmatic reset — use a generation counter
The Workspace switcher selectbox (Step 5) is keyed by user + a generation counter
(`wa_workspace_selectbox_{user}_{gen}`). Without the counter, after `create_workspace()` sets
`wa_workspace_id` to a NEW Workspace and reruns, the keyed selectbox keeps its previous value,
so `selected_ws != current_ws` and the widget silently fights the programmatic intent — the
new Workspace never becomes selected (A1), and a stale value would have to be force-reset. A
manually-changed selection or a create bumps `wa_ws_gen`, making Streamlit treat the widget as
new and re-initialize from `index`. This is the fix for the Step-5 item-2 double-answer trap
(§5.2.1). The counter is intentional, not cruft — do not "simplify" it into a bare key.

### 2026-09-11 — Clean-clone verification + A24 history check (final sign-off)
Verified from a fresh `git clone` of `git@github.com:RafaelTacconi/OC_KB_Pro.git`
into a temp dir: `python -m venv` + `pip install -r requirements.txt` +
`python -m pytest tests/ -q` → **55 passed** (34s; HF-HUB-ONLINE, embedding model
downloads occurred in the venv cache). A24 against HISTORY (not the working
tree): `git log --all --full-history -- .env` → empty; a full-object scan
(`git rev-list --all --objects`) shows the ONLY `.env*` path ever committed is
`.env.example` (the empty template). No real key or base URL exists in the repo's
history. `ACCEPTANCE_MATRIX.md` (repo root) records per-criterion proof for
A1–A25, including which are not verifiable without a live endpoint / documents.

### 2026-09-11 — A12/A13 caveat (verify against a real failure sometime)
The §7.1/§7.6 AppTest suites prove the error path against a **monkeypatched
`call_model` that raises `RuntimeError("forced model failure …")`**, not against
a real provider failure. The handler is exercise-true, but the real failure
surface (SDK exception shapes, timeouts mid-stream, auth errors) is unverified.
When a live endpoint exists, a single manual send against a bad key/slug would
close this gap; it is not code that needs changing.

### 2026-09-11 — OCR is scoped-and-deferred (out of scope for the PoC) — SPEC §15.1
Reading embedded image content (OCR / image extraction) is DECIDED out of scope
for this PoC. Reasons recorded: (1) native Tesseract + poppler binaries are
required on Windows and are not pip-installable (the same system-dependency
chain the repo's docstrings flag as fragile); (2) OCR is minutes-per-file vs
milliseconds for text — prohibitive for an image-heavy corpus; (3) citations
would be file-level only (no figure/region linkage); (4) DOCX image reading
needs a vision model, not just OCR. Instead, the app counts embedded images per
file and shows an Owner note (§15.1) so the gap is visible without attempting to
read the images. Authority: owner decision 2026-09-11; do not reintroduce OCR.

### 2026-09-11 — Embedded-image count is a FLOOR, not an exact measure — SPEC §15.1
The per-file `image_count` (parsers + `sources.image_count`) counts raster
images only. Vector diagrams and curve-rendered text may not register as
countable images, so the count is a lower bound. It flags the PRESENCE of images,
never their semantic content or how much procedure is lost. It is a UX safeguard
(and an Owner-facing measurement aid), not a guarantee. Do not present it as
exact.

### 2026-09-11 — OPEN-13 was only missing from my summary, not from the spec
The 12-unanswered count: when listing open items for the owner I gave 11
(OPEN-1..10 + OPEN-12), omitting **OPEN-13** (the deployed app has no
authentication — anyone reaching the port can sign in as Owner and delete any
Workspace). It IS present in SPEC §11 (the addendum row) and in memory.md's
Decision log; only my summary dropped it. It belongs on the decide-before-test-
users shortlist — §14.1 flags it as a deployment decision (network-restricted
host vs a gate). No spec fix needed.

### 2026-09-11 — chunk_text accumulates FRACTIONAL tokens; do not round per paragraph
`ingestion/chunking.py::chunk_text` accumulates `len(para.split()) * WORDS_TO_TOKENS` as a
FLOAT across paragraphs and casts once at finalize (`int(current_tokens)`). The §7.8
`estimate_tokens` de-dupe moved the shared function to `models/context_budget.py` and made
`chunking` import it, but left this accumulation EXACTLY as-is. Switching to per-paragraph
integer rounding would shift chunk boundaries (`target_tokens` comparisons happen on the
fractional running total), and the existing `test_chunk_text_respects_target_size`'s ±60
tolerance might not catch the shift. Guarded by
`test_chunk_boundaries_unchanged_after_dedupe`, which pins the layout against a reference
implementation. Do not "simplify" the float arithmetic.

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

### 2026-09-11 — Steps 3 and 4 are landed TOGETHER in one commit
SPEC §9 lists Step 3 (schema/migration) and Step 4 (multi-Chat UI) as separate steps, but
from the 2026-09-11 session they ship as one commit. Split up, `_save_message()` would write
`chat_id = NULL` between the two commits — the exact state A10 forbids, self-healed only by
the next `migrate_db()` run. Landing migration + the Chat features that use `chat_id`
atomically means no NULL-chat_id window ever exists. Decision recorded in `state.md`.
Authority: **Owner delegated the choice on 2026-09-11; the agent chose combined** — the owner
did not make this call, so this is not an "answered by project owner" entry (A19). Same
one-commit pattern as Step 2b (registry split + picker + adapter shipped together).

### 2026-09-11 — Embedding-model load failures are now remembered for the session
`ingestion/embedding.py::_get_model()` previously only cached a successful load, so every
call after a failure re-attempted the model download. Once §7.3 made `hybrid_search()` catch
instead of crash, every chat turn would have re-attempted it — paying a network/model timeout
per turn. Changed (owner-approved, see decision for Step 1 — point 3): a failed load is stored
in `_model_load_error` and every subsequent call raises fast with a short message pointing at
the root cause; recovering requires an app restart once the model/network works. Logged as a
deviation from the previous behaviour at the owner's request.

### 2026-09-11 — The failure cache also affects ingestion — supersedes part of the entry above
The `_model_load_error` cache is **module-global and shared with ingestion**: `embed_batch()`
(called by `ingestion/pipeline.py::ingest_source()`) goes through the same `_get_model()`.
So one transient embedding-model failure during a chat now also makes **uploads fail fast
until the app restarts** — the owner flagged this side effect was not named in the entry
above. Consequence: a flaky network that fails once can silently take down chat AND uploads
for the rest of the session with no retry. Accepted for the PoC (restart is the recovery);
recorded here complete.

---

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

### OPEN-4 — Membership on a new Workspace — 2026-09-11 (supersedes entry above)
Question: Who is a member of a newly created Workspace (`SPEC.md` §5.3)?
Outcome: **The interim ("all TEST_USERS") is being REPLACED by the build of
per-Workspace membership management (level (a) from the owner's scoping).** This
CLOSES OPEN-4: the Owner decides membership per Workspace instead of every
TEST_USER being auto-added. The prior interim entry above is superseded.
Authority: Answered by project owner on 2026-09-11 (decision to build (a); agent
implements).
Consequence: `create_workspace()` no longer adds every TEST_USER; only the
creating Owner is added. The §5.3 interim rule and its "no private Workspace"
consequence are invalidated. Members must now be added explicitly via Manage →
Users.

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

### OPEN-13 — Authentication on an internal deployment — 2026-09-11 (supersedes entry above)
Question: Where does authentication live for the internally deployed app (`SPEC.md` §14.1)?
Outcome: **Deliberately deferred to the DEPLOYMENT boundary, not built in app.** The owner
chose real authentication at the network/reverse-proxy layer in front of the Streamlit port
rather than in-app login (decision 2026-09-11). Explicit recorded consequence: until that
port is network-restricted, ANYONE who can reach it can select "Alex (Owner)" and delete a
knowledge base — this must appear in the deployment notes, not just the journal.
Authority: Answered by project owner on 2026-09-11 (deferred to deployment layer); agent does
not build in-app authentication.
Consequence: The impersonation risk is real and open until the deploy-time gate exists.
Per-Workspace membership (OPEN-4 build) does NOT close it — it only gates visibility, not
identity.

### OPEN-14 — Is the port already network-restricted? — 2026-09-13
Question: Is the Streamlit port network-restricted to entitled users, or merely reachable on
the internal network by anyone who knows the address?
Outcome: Unverified. Interim: treat "anyone who can open the app is already authorised" as an
assumption, not a fact.
Authority: Deferred — not reached.
Consequence: §17 F10's identity model rests entirely on this premise. If the port is merely
reachable, self-declared identity is not an access control at all. Related to OPEN-13 but not
the same question — OPEN-13 asks whether a gate is needed, OPEN-14 asks whether one already
exists.

### OPEN-2 — `call_model` signature and registry accuracy — 2026-09-14 (addendum; neither entry above changes)
Question: Are the 256k context figures in `models/registry.py` correct?
Outcome: Still open — the real `context_window_tokens` per model is unconfirmed; 256k remains
an assumption. **Raised in severity by SPEC §20:** a calling system pasting case context can
exceed the real limit and the provider will reject the request. It must be confirmed against the
live endpoint **before the API is built**.
Authority: Deferred — not reached.
Consequence: `fits_in_context()` keeps using 256k; §20 must not ship on that assumption.

### OPEN-15 — Should the API response include a `grounded` flag? — 2026-09-14
Question: Should the §20 API response include a `grounded: true/false` flag?
Outcome: Deferred — not reached. All three options recorded: (a) parse the model's own
"(Source: …)" text — the approach rejected for the citation chips (§7.11); (b) ask the model to
declare its own honesty; (c) return `sources` and let the caller decide from an empty list. None
chosen; §20.3 forbids adding the field until this is answered.
Authority: Deferred — not reached.
Consequence: A wrong flag is worse than no flag because a calling system branches on it
automatically with no human reading the answer — higher-stakes than the chip relabelling was.

### OPEN-16 — Retrieval under pasted case context — 2026-09-14
Question: Does retrieval degrade when case context is pasted into the question (§20.1, §20.2)?
Outcome: Deferred — not reached. Unmeasured risk. Search uses the ENTIRE question text as the
query, so account numbers, amounts, and dates become search terms that appear nowhere in the
procedures; retrieval may get worse exactly when the question is richest. Must be measured
(short / medium / long context) before the §20 API design is finalised.
Authority: Deferred — not reached.
Consequence: The intended API workflow (caller pre-processes a case and sends it inline) rests
on an untested assumption about retrieval quality.

### OPEN-17 — Chat retention — 2026-09-14
Question: Should only the last 10 conversations be kept?
Outcome: Deferred — not reached. Both positions recorded: (a) cap at 10 to keep the selector
manageable; (b) do not delete — chats are plain text, storage is not the constraint, and
deleting a user's work to reclaim space that was never short is a poor trade. The cluttered
selector is a display concern (show recent, collapse the rest), compounded by the missing
delete action (OPEN-6 / OPEN-8).
Authority: Deferred — not reached.
Consequence: No retention policy and no deletion are built.

### Flaky test — `test_chat_error_handling.py` intermittent failure — 2026-09-15
Question: Why did `tests/test_chat_error_handling.py::test_failed_turn_persists_question_and_retry_does_not_duplicate`
fail once during the §19/§20 pass, in a full-suite run that took 68s against a normal ~32s, while
passing in isolation and on re-run?
Outcome: Unresolved. Leading theory: an **`AppTest` timeout under load** — the test builds the real
app with `AppTest.from_file(..., default_timeout=30)` and performs several `.run()` calls; under a
slow run one can exceed 30s. It is **not waiting on anything external** (the model call is
monkeypatched to raise, and the DB is a temp file), so if it is a timeout it is a machine-load /
default-timeout artefact, not a dependency. Not reproduced since.
Authority: Deferred — not reached.
Consequence: The suite can report a spurious failure under load, and a real regression in the §7.1
error path could be masked by assuming this test is flaky. **Do not weaken or skip the test.** If it
recurs, capture the traceback and consider raising `default_timeout`.

### Deferred fix — xlsx row counting (title block) — 2026-09-15
Question: How should `parse_xlsx` count data rows when a sheet has a title/subtitle block above the real header?
Outcome: **Approved as a diagnosis, NOT approved to build.** Root cause and a proposed fix are in
the Codebase discoveries entry of 2026-09-15. Two owner reservations must be carried into any
eventual build:
1. The proposed header-detection rule (first row whose non-empty width equals the sheet's maximum
   width) is a heuristic like the heading one. If it picks the wrong row, **every column is
   mislabelled — a worse and quieter failure than a wrong count.** Any fix MUST have an obviously
   safe fallback when the shape is ambiguous, and must **prefer being unsure to being confidently
   wrong**.
2. It forces **re-ingestion of every `.xlsx` in every Workspace** (the owner has already re-uploaded
   the corpus three times). The fix should travel with **other ingestion work**, so one re-upload
   buys several improvements.
Authority: Deferred — not reached (owner decision 2026-09-15: diagnosis approved, build not approved).
Consequence: The defect stands; do not build the xlsx fix alone. Not lost, not to be re-litigated.

### Staging API + Tier 1 logging — SPEC §19.6 / §20.9-§20.13 — 2026-09-15
Question: How to expose the service for end-to-end staging use while OPEN-13/OPEN-14 remain
unanswered, and how to log it?
Outcome: **Built.** (a) **Tier 1 logging only**, into a separate `data/logs.db`; the main database is
unchanged. (b) The API is a **separate process** (`python -m service.api`) that reuses
`retrieval/`, `prompting/`, and `models/`; no API code in the Streamlit app. (c) **Loopback-only
binding (`127.0.0.1`), enforced at startup by refusing to start otherwise and naming OPEN-13/OPEN-14
— this is the OPEN-14 containment: unreachable by construction, not by policy.** (d) **A single
static `KB_API_KEY` shared secret**, explicitly temporary: no per-caller identity, no revocation, no
audit. (e) No rate limiting, no Tier 2, no per-caller membership. (f) **SQLite concurrency:** the log
DB uses WAL + `busy_timeout`; the API only READS the main DB, so it adds no writer and **no main-DB
schema change is needed**.
Authority: Answered by project owner on 2026-09-15 (owner directed the staging build and its
constraints; OPEN-13/14/15/16 deliberately left unanswered).
Consequence: The staging API is reachable only from the same machine; production remains blocked on
OPEN-13/OPEN-14, and `KB_API_KEY` must be replaced by §17 F10's identity model. The refusal rate is
computable for the API's empty-retrieval case (`outcome='refused'`); the wider refusal signal is
still OPEN-15 (SPEC §19.6).

### Interim refusal signal — scope fixed 2026-09-15
Question: Which refusal signal should Tier 1 record?
Outcome: **Interim, owner-scoped, and applied identically on both surfaces.** On a completed turn
`outcome='refused'` iff `chunks_retrieved == 0`, else `answered`; failures are `error`. **UI fix:**
`ui/chat_view.py::_run_turn` previously logged `answered` on every success, so the UI — nearly all
traffic — reported a **0% refusal rate**; it now applies the same rule as the API. The UI still
**calls the model on zero chunks**; no short-circuit was added (owner: do not add one). **This signal
UNDER-COUNTS refusals:** a turn where chunks came back but the documents did not answer logs
`answered`. That wider question is OPEN-15 and is deliberately not answered here.
Authority: Answered by project owner on 2026-09-15 (the scope of the interim signal only; OPEN-15
itself remains open).
Consequence: The refusal rate is usable and comparable across UI and API, but is a **floor**, not the
full rate, until OPEN-15 is answered by the owner.

### OPEN-2 staging deviation — named 2026-09-15
Question: SPEC §11 OPEN-2 requires the real `context_window_tokens` to be confirmed against the live
endpoint before the API is built. It was not.
Outcome: **Named staging deviation; not an answer.** The staging API was built on the unconfirmed
256,000-token assumption. The 256 KiB request-body cap (SPEC §20.12) is a **flat size guard,
unrelated** to the model's real context limit: a request under 256 KiB can still exceed the
provider's real limit and surface as a `502 provider_error` — **most likely during the OPEN-16
measurement**, where long case context is the point.
Authority: Deferred — not reached (OPEN-2 remains open; this records the deviation, it does not
answer OPEN-2).
Consequence: A staging API request with large case context may fail as 502 for a reason that is
really an unconfirmed context window. Confirm against the live endpoint before production.

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

### 2026-09-11 — Cross-document recall miss: MLRO→SAR filing timeline (Step 8 case)
A live end-to-end question answered well from three files but STOPPED SHORT on a
fact that WAS in the corpus: it said the MLRO-to-SAR filing timeline "wasn't in
the sources", when it is in `AML_Escalation_Procedure.docx` Step 3 — that chunk
just did not make the top-5 hybrid result for that query (the file has 5
steps/chunks; other chunks outranked Step 3). This is a concrete, reproducible
case for the §9.3 offline evaluation: a question whose expected source chunk is
in the corpus but below the top-5 cutoff. Do NOT change top_k /
MAX_RETRIEVED_TOKENS to chase it — measure it first. The chunk exists; the
ranking lost it.

### 2026-09-11 — unstructured PDF section-titles are NOT trustworthy (verified mechanism)
The citation "AML_Policy.pdf — Financial Crime Oversight Committee" pointed at a
SENTENCE from inside section 3, not a heading. Cause: `partition_pdf`'s layout
heuristic classifies visually-emphasized body text as `Title`/`Header` elements,
and `_group_unstructured_elements` promotes ANY such element to `section_title`.
Verified on a synthetic DOCX that REAL heading styles produce clean titles, so
the problem is PDF-specific (the layout model, not the grouping code). Fix would
be either: (a) for PDF, only trust element types that are genuine headings
(unstructured still over-labels), or (b) accept `Page N`-style titles from the
pypdf fallback for PDFs. Not built 2026-09-11; the owner reported it and the real
AML_Policy.pdf is gone (data/ was cleaned), so no repro file exists. The citation
section text is a UX trust problem — a wrong "section 3" undermines citations.

### 2026-09-11 — unstructured PDF headings: trust SHAPE, not element type
`unstructured.partition_pdf` is unreliable for heading detection on real PDFs:
it labels wrapped body sentence FRAGMENTS as `Title` ("Financial Crime
Oversight Committee.", "channel for Severity 1.", "than 15 minutes.") while the
REAL numbered section headings arrive as `ListItem` ("1. Scope", "2. Escalation
Timeline"). Keying section titles on `Title`/`Header` alone therefore picks
exactly the wrong elements. Fix (built): `_looks_like_heading` classifies by
shape — a numbered pattern (`^\d+(?:\.\d+)*[.)]?\s+\S`) is a heading whatever
its type; a `Title`/`Header` is a heading only if short, not ending in `.`, and
starting uppercase/digit. Heuristic; validated against the observed element
stream in `tests/test_parser_headings.py`. A doc with un-numbered or
sentence-style headings could still misclassify — revisit if the real corpus
shows it.

### 2026-09-13 — Heading heuristic is UNVALIDATED against real documents
`_looks_like_heading` (numbered pattern / short / no trailing period /
uppercase-or-digit start) was derived from the nine synthetic test files only.
The real corpus is back-office **bank procedures**, whose heading styling is
unknown. **Do NOT tune it further against the synthetic corpus.** It must be
re-checked against real documents (and likely adjusted) before section citations
are trusted. Until then, treat section titles as best-effort. See SPEC §7.10
"A29 caveat".

### 2026-09-13 — Chat export is a conscious privacy decision (SPEC §16.2)
Building a Markdown **chat export** (A34) means internal procedure content —
user questions, model answers, and cited source filenames — leaves the app as an
**uncontrolled local file**. Accepted for this PoC because the owner runs it on
their own machine. **Must be revisited before other people use the tool**, and
before any deployment (OPEN-13). Recorded as a conscious decision, not a
default.

### 2026-09-11 — Expiry tests used the LOCAL date; production uses UTC
`models/credentials.py::api_key_status()` compares against
`datetime.now(timezone.utc).date()`. The expiry tests in
`tests/test_provider_config.py` built their dates with `date.today()` (local),
so they failed by one day whenever the machine's local date was ahead of UTC.
Fixed with a `_utc_today()` helper. Rule: any test touching date-based status
must use the SAME clock the production code uses (UTC).

### 2026-09-11 — root cause: the conftest `data/` guard vs the running app — you only delete what is safe once the guard can't mislead
The repo `data/` directory was deleted TWICE this session (once for the conftest
"no data/ at repo root" assertion, once by an over-broad `Remove-Item -Force
data` before a pytest run), destroying the user's uploaded corpus + conversations
each time. Root cause is NOT "don't run Remove-Item": it is that the guard
required `data/` to be ABSENT at the repo root, while the running app legitimately
CREATES it. So any workflow that (a) ran the app and (b) then ran pytest forced a
choice: delete the app's data or reject the test run. FIXED 2026-09-11 by making
the guard snapshot-compare (`_repo_data_snapshot()`): pre-existing `data/` from a
stopped app is tolerated and untouched; the TEST SUITE still fails if it creates,
modifies, or deletes any repo `data/` file. The guard never weakens. Second
lesson: verify what `data/` belongs to (live app vs test artefact) BEFORE deleting
it — a running app's DB is not a disposable fixture.

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

### 2026-09-13 — The seven grounding failures are prompt-level, not retrieval — no parameter changed
Owner hand-ran the adversarial suite on **2026-09-13** and confirmed **seven** failures, all the
same shape: the model **detects the gap, says so, then answers past its own refusal in the same
breath** — supplying general knowledge, a "typically", a textbook definition, or a value/date it
was never given. Cases: (1) "What's the deadline?" answered 12h as if unique though the corpus has
at least four; (2) derived "2026" for destroying 2019 files from a 3-year premise the question
invented, when retention is 7 years from the END OF THE CUSTOMER RELATIONSHIP — never given;
(3) declared the 12-hour clock "runs continuously" when overnight/weekend handling is genuinely
unspecified; (4) defined a SAR after correctly saying the corpus never does; (5) described what
training policies "typically" contain after noting training is not covered; (6) computed 04:00
Saturday without flagging weekend handling as unspecified; (7) claimed policy and severity matrix
"agree" on Severity 3 when only the matrix mentions it. **Common root cause is not search** — the
right chunks were retrieved and the model SAW the gap; the system prompt allowed the answer to
continue after a stated gap. **The fix is prompt-level ONLY**: `prompting/assemble.py::SYSTEM_POLICY`
gained five absolute grounding rules (SPEC §18.1, A37–A41). `retrieval/` and every retrieval
constant (`top_k`, `MAX_RETRIEVED_TOKENS`, `rrf_k`, `candidate_pool`, chunk sizes) were **not**
touched. The seven are kept as a named hand-run regression set in `GROUNDING_REGRESSION.md`; no
automated test may call the live model.

### 2026-09-13 — Flaky test: `test_chat_error_handling.py` failed once under load (open reliability question)
`tests/test_chat_error_handling.py::test_failed_turn_persists_question_and_retry_does_not_duplicate`
failed once intermittently during a full-suite run that took **68s against a normal ~32s**; it passes
in isolation, and the full suite passed on re-run. Suspected **timeout flake** (the AppTest default
timeout under a slow run), not an assertion failure. **Not caused by the pass it occurred in** (that
pass changed documentation only — no code or test) and **not yet diagnosed**. If it recurs, capture
the traceback and consider raising the AppTest `default_timeout`; do not weaken the test.

### 2026-09-15 — A29 heading heuristic validated against a real bank procedure (first real-document check)
The shape-based `_looks_like_heading` rule (SPEC §7.10, A29) was validated against a **real bank
procedure** for the first time (four documents — two .docx, one .xlsx, one .pdf — 19 questions).
Properly styled Word headings (numbered, Heading 1/2/3) produced the **correct section title in
every citation** — e.g. "3. The escalation rule", "5. Reading the scanned claim advice". The
2026-09-13 caveat ("validated only against the synthetic corpus") is now **partially discharged: it
holds for properly styled Word headings.** It remains unvalidated for **PDFs with sentence-style or
unnumbered headings.**

### 2026-09-15 — Measured image gap: real but narrower than assumed
Real-corpus test (2026-09-15): two .docx held **9 embedded images**, two of them substantive (a full
process-flow diagram and an annotated scanned document). Questions whose answers existed **only
inside images** were correctly **refused** in all three cases tested. Questions whose answers were
duplicated in text or in the companion .xlsx were answered correctly. Conclusion: the image gap is
**real but narrower than assumed**, because well-written procedures tend to repeat diagram content in
prose. **§17 F8 stays deferred; this measurement does not reopen it.**

### 2026-09-15 — xlsx row counting is wrong when a sheet has a title block (real-corpus defect; fix proposed, not built)
`ingestion/parsers.py::parse_xlsx` reads every sheet with `pd.read_excel(..., sheet_name=None)` at
the **default `header=0`**, so it blindly treats **physical row 1** as the column header. A sheet
with a title/subtitle block above the real header is misread: the title becomes the column names, and
the real header and subtitle become ordinary data rows. The auto-summary
`Sheet '…' has {df.shape[0]} rows` is then `physical_rows − 1`, **not** the true data-row count.
Verified on a synthetic sheet (1 title + 1 subtitle + 1 header + 42 data = 45 physical rows): the
summary said **"has 44 rows"**, the markdown table carried 44 data lines (plus a markdown header +
separator = 46 `|` lines), and the true answer (42) appeared only incidentally inside a title cell
now rendered as data. There is **no row-number prefix** (`index=False`) and **no marker for the real
header**. The model answered **"45 rows"** — a confidently wrong count, exactly the failure the tool
must not produce. Also note `chunk_text` splits the 24-token summary from the 542-token table into
**separate chunks**, so a count in the summary is not guaranteed to travel with the table.
**Proposed fix (NOT built; owner approval pending):** read with `header=None`, locate the real header
as the first row matching the sheet's maximum non-empty-cell width (skipping a narrower title block),
count only rows after it, and render an explicit 1-based row-number column so the last number is the
count and line-count inference is impossible. An ingestion change here requires **re-processing every
xlsx Source** (docx/pdf unaffected).

### 2026-09-15 — The answer pipeline WAS cleanly callable outside the UI (two small frictions)
`retrieval.hybrid_search`, `prompting.assemble.build_prompt`, and `models.router.call_model` were
callable from the new `service/engine.py` with **no changes and no Streamlit import**. Two frictions
worth recording: (1) `ui/chat_view.py::_run_turn` cannot be reused by the API — it lives in a
Streamlit-importing module and also persists Chat rows, which §20.8 forbids for API calls — so the
engine has its own small orchestration. (2) `_load_workspace()` exists only inside
`ui/chat_view.py`; the engine keeps its own 5-line read rather than importing `ui` (which would pull
Streamlit into the API process). Nothing needed a workaround; if a third caller appears, those two
reads should move to a non-UI module.

### 2026-09-15 — `top_k=5` now lives in two surfaces and can silently drift
`top_k=5` is hardcoded in **both** `ui/chat_view.py::_run_turn` and
`service/engine.py::answer_question`. The two surfaces now carry the same retrieval constant in two
places; changing one and not the other would make the UI and the API retrieve different numbers of
chunks with no test catching it. **Note, not a refactor** (owner direction): do not move it yet. If a
third caller appears, or when the OPEN-16 measurement suggests a change, centralise it.

### 2026-09-15 — the `chunks` table stores nothing page-like (the API `page` field is an INGESTION gap)
The `chunks` table has **no page column**: `chunk_id, source_id, workspace_id, section_title, text,
embedding_text, embedding, token_count, created_at`. The PDF fallback parser sets
`section_title = "Page N"`, but the primary `unstructured` path uses real headings and discards the
page. So the API's always-null `page` (SPEC §20.13) is an **ingestion gap, not a rendering gap** —
populating it would require capturing and storing a page number during parsing, i.e. an ingestion
change and a corpus re-processing.

### 2026-09-15 — OPEN-16 first live measurement: rank drift vs. distinct-document count (EVIDENCE ONLY; OPEN-16 REMAINS UNANSWERED)
First live run of `scripts/measure_open16.py` against `aml-workspace` on 2026-09-15, question
*"What triggers an enhanced due diligence review?"*, three ways (bare / short case context /
long case context). This records observations, not a finding. **No retrieval setting was changed
(`top_k`, `MAX_RETRIEVED_TOKENS`, `rrf_k`, `candidate_pool`, chunk sizes all untouched), no
acceptance criterion was added, and OPEN-16 is not answered, resolved, or narrowed to a mechanism
by this entry.** All three runs answered correctly; the correct chunk (`AML_Policy.pdf`,
"4. Enhanced Due Diligence Threshold") was retrieved every time, but its rank drifted as context
grew: **bare = rank 1, short context = rank 1, long context = rank 3.**

- **Failure mode observed is RANK DRIFT, not an outright miss.** With five retrieval slots, drift
  of this size would eventually push a correct chunk off the list on a larger corpus. On the nine
  documents of this run it did not.
- **Chunks that overtook it under long context were "2. Escalation Timeline" and "5. Record
  Retention".** A **PLAUSIBLE reading — recorded explicitly as a HYPOTHESIS consistent with one
  observation, NOT a demonstrated rule and NOT a confirmation of the OPEN-16 mechanism — is that
  the pasted case data (dates, amounts, account references) matched timeline/retention language.**
  It has not been tested.
- **DISTINCT-DOCUMENT COUNT, which cuts the other way:** the bare and short runs each returned 5
  chunks from only **TWO distinct documents**; the long-context run returned 5 chunks from
  **THREE**, and was the only run to retrieve `AML_Thresholds.xlsx`, which holds the per-band
  overrides. Extra context **broadened what was considered as well as reordering it.**
  Cross-reference: the existing Step 8 finding that top-5 often considers far fewer than five
  distinct documents.
- **The two observations PULL IN OPPOSITE DIRECTIONS.** Rank drift is evidence that case context
  HURTS retrieval; the widened distinct-document count is evidence that it HELPS. They come from
  the same single run and NEITHER HAS BEEN WEIGHED AGAINST THE OTHER. Nine documents cannot settle
  it. **STANDING INSTRUCTION: whoever re-runs this at scale must measure BOTH — the rank of the
  correct chunk AND the number of distinct documents retrieved — because measuring rank alone would
  show only the pessimistic half and would look like a conclusion.**
- **SAMPLE SIZE:** exactly ONE question, with ONE case-context payload, on a nine-document
  synthetic corpus. Nothing here generalises. A re-run needs multiple questions and multiple
  payloads before any of it counts as a finding.
- Every source returned `page=None`, as expected (ingestion gap, already recorded above).
- **NOT recorded as a finding:** subjective answer quality — one question, no controlled comparison.

### 2026-09-15 — staging API first live run: operational notes (observations, not defects)
From the same first live run as the OPEN-16 measurement above:
- The API **loads the embedding model at startup (103/103)**. Running it alongside Streamlit means
  **two copies of the model in memory.**
- The API **exited silently once on first launch**, printing its banner and returning to the prompt
  with no error. Not reproduced on re-run. Recorded as an **observation, not a defect — do not
  investigate or change anything.**

### 2026-09-15 — DEFECT: over-refusal on retrieved material (positive-case failure; prompt-level; no fix)
Workspace `d93d5cd12269400e9298c535062afc65` (NBCA), staging API, 2026-09-15. Question
*"Where do escalated breaks go and who receives them?"* → answer *"The documents do not cover
where escalated breaks go or who receives them."* **That refusal is WRONG; the evidence is the
stored chunks, inspected read-only, not inferred:**

- Rank-1 retrieved chunk was `3cbb9bc6e5834b72883fd8467c101e6d`
  (`NBCA_Daily_Operations_SOP.docx`, "1. What this process is and why it exists", 353 tokens /
  1,612 chars) and **provably contains** "Before the 11:00 escalation pack goes out to the desk
  heads…".
- The Glossary chunk `ee3eab046b4948dda80ad5ebc73e6ff5` was **also retrieved** and defines
  "Escalation pack" as the 11:00 summary sent to desk heads.
- The section is **ONE chunk** — not split, no boundary effect, title and body in the same chunk.

**Ruled out explicitly (do not re-litigate):** NOT a retrieval failure (the correct chunk ranked
1); NOT a chunking failure (single chunk, boundaries inspected); NOT an ingestion failure (the
text is present and was inspected directly); NOT the "title without payload" concern (the payload
was in the chunk). **This is PROMPT-LEVEL — the same layer as the seven §18 grounding failures.**

**Why this class of failure was invisible:**
- §18 and `GROUNDING_REGRESSION.md` test that the system REFUSES when it should. **Nothing tests
  that it ANSWERS when it can** — the entire test history hunts fabrication; this is the opposite
  failure and no suite covers it.
- An unwarranted refusal is indistinguishable from correct behaviour to a reader, because refusal
  is the tool's advertised virtue.
- **Refusal rate (A46) cannot detect it:** the metric counts refusals, not whether they were
  warranted; a rising rate would look like the documents having gaps.
- Both observed refusals returned **NON-EMPTY sources**, so Tier 1 logs them as
  `outcome='answered'` — they do not appear in the refusal count at all. A concrete instance of
  the under-count already documented in §19.6.

**SECOND OBSERVATION, same run set.** Question *"What is the escalation path when a nostro break
cannot be matched?"*: **bare** refused but usefully — it distinguished the flagging rule from the
routing, citing SOP section 3, with "3. The escalation rule" at **rank 5**; **short and long
context**: "3. The escalation rule" dropped OUT of the top 5 entirely and the answers degraded to
a bare "not specified". Distinct documents retrieved: **2 / 2 / 2** across all three conditions —
**NO widening**, unlike the AML run (2 / 2 / 3). Recorded as further **OPEN-16 evidence;
OPEN-16 REMAINS UNANSWERED.** The NBCA run **contradicts** the AML run on distinct-document
widening — which is exactly why both must be measured at scale.

**NEGATIVE CONTROL — PASSED.** *"What is the bank's policy on employee overtime pay?"* (outside
the corpus) refused correctly in all three conditions, including with long reconciliation case
context prepended. **§18 grounding held under pasted case data.** Recorded as evidence, not as a
test result (`measure_open16.py` asserts nothing).

**Two separate threads, NOT today's problem (record only — do not investigate, do not tune):**
1. The SOP's "Key contacts" chunk `3d03f4c16bef464583963caee8d0cb1a` (79 tokens; Raman, Meyer,
   Dubois, Baumann) has NEVER been retrieved in roughly 40 source slots. *"Who owns FR03
   escalations?"* was answered correctly, but from
   `NBCA_Exception_Matrix_Quick_Reference.xlsx` "Contacts & Ownership" instead. **Possible
   short-chunk ranking disadvantage.**
2. That same chunk carries a page-footer fragment ("Page of | Internal use – Custody
   Operations"). Cosmetic. **Park it with the deferred xlsx header fix and the page-number
   ingestion gap so one re-ingestion buys all three.**

**SCOPE — do not overstate:** one question, one corpus, four documents. The **MECHANISM is
demonstrated** (the text was provably in the retrieved chunk and was not used); the **FREQUENCY
is completely unmeasured**. **No fix is approved and none is proposed.** A fix needs a regression
set of questions whose answers are known to be in the corpus — the mirror of
`GROUNDING_REGRESSION.md` — which does not exist yet.

### 2026-09-15 — Positive-case regression set built; lives OFF-REPO (NBCA real corpus)
Built `GROUNDING_REGRESSION_POSITIVE.md` (14 cases; all `NOT YET RUN` except the known `FAIL`
PC-01) — the **answer-when-it-can** mirror of `GROUNDING_REGRESSION.md`. It is **corpus work**:
every case was verified by reading the NBCA chunk TEXT directly (never by section title) and
carries a durable **locating phrase** because `chunk_id`s are regenerated on re-ingestion.
Coverage: 4 simple lookups, 3 xlsx-table cases, the SOP "Key contacts" chunk `3d03f4c1…`
flagged **AT RISK**, 4 short-chunk cases, one two-chunk case, and one PDF case (the PDF
duplicates the SOP/xlsx and is **not uniquely answerable**). **It is NOT YET RUN and no
retrieval/prompt setting is changed by it.** The file is written to the repo folder but is
**deliberately NOT committed**: it is built on the real anonymised **NBCA** bank procedure
(staff names, desk codes, internal process detail) and this repo is public —
`GROUNDING_REGRESSION.md` is committed only because it used the synthetic corpus. `.gitignore`
now lists it as a backstop. **The file must be moved off-repo (owner's desktop, with the other
off-repo test assets); never commit it.**

### 2026-09-15 — PDF section titles are WRONG: A29 caveat now has evidence against it (record only; owner to decide)
In `NBCA_Quick_Reference_Card.pdf`, chunk `29b4dc3fd7c2493799d4c9866bc41ae5` contains the three
escalation conditions but carries `section_title` **"CLAIM_NO_MATCHING_BREAK"** — a heading that
belongs to different content. Section titles are what the **citation chips display**, so a PDF
source can be cited under a **wrong section name**: the answer correct, the citation wrong, in a
tool whose value rests on **checkable citations**. This bears directly on **A29**, recorded as
**partially discharged** — correct for real numbered Word headings, **unvalidated for PDFs with
sentence-style headings**. It is now **validated for this PDF and it FAILS**: the caveat now has
**evidence against it.** **A29's status is NOT changed, `SPEC.md` is NOT edited, and no criterion
is added — the owner must decide what follows.** **No fix, no investigation.**

**LEAD (not a finding):** the same PDF's chunk text has **TAB characters between individual
words**, indicating a **mangled parse**. This **may** contribute to the PDF never having been
retrieved in ~40 observed source slots. **Untested — do not investigate and do not tune
anything.**

### 2026-09-15 — Positive set run: 15 bare questions → 14 correct, 1 refusal; earlier over-refusal conclusion CORRECTED; two suspicions WITHDRAWN
`GROUNDING_REGRESSION_POSITIVE.md` (off-repo) run **bare** via `scripts/run_question_set.py`
against workspace `d93d5cd12269400e9298c535062afc65`, staging API, **2026-09-15**: **15 questions,
14 answered correctly** against the expected answers, **1 refusal**.

**CORRECTION to the entry "DEFECT: over-refusal on retrieved material" (2026-09-15).** That
entry was written from **ONE observation** and implied a general tendency; on 15 verified
positive cases the rate is **1/15**, not a general tendency. The original entry is **left
unedited** — this entry corrects and cross-references it.

**PC-01 reproduced — a borderline case, recorded as an OPEN JUDGEMENT CALL (not a proven
defect).** "Where do escalated breaks go and who receives them?" refused again, with the same
answer-bearing chunks retrieved (SOP section "1. What this process is and why it exists" +
"Glossary"). **Reproducible, not noise.** Nuance: in the corpus the escalation pack's destination
appears only **INCIDENTALLY** — a subordinate clause about an 11:00 deadline, plus a glossary
definition; all **14 passing cases state their answer as a declarative fact**. The refusal **may**
be the model distinguishing "mentioned in passing" from "specified", which is close to **intended
§18 behaviour**. Same routing weakness in the SOP that produced the earlier "three destinations,
names two" finding. **Open judgement call — decide defect vs correct strictness; no fix.**

**Two recorded suspicions REFUTED — WITHDRAWN explicitly (do not re-litigate):**
1. "SOP 'Key contacts' chunk `3d03f4c1…` never retrieved / short chunks may lose on length" —
   **REFUTED**: it was retrieved at **RANK 1 on two questions** in this run. The short-chunk
   suspicion is **withdrawn**; it rested on too few questions.
2. "The PDF has never been retrieved in ~40 slots" — **REFUTED**: the PDF appeared in **5 of 15**
   questions. **Withdrawn** as a sampling artefact.

**PDF section titles — CONFIRMED USER-VISIBLE.** Across multiple retrieved PDF sources, observed
`section_title` values include **run-on body text and page furniture** — e.g. a title beginning
"6 Apply the escalation rule", and another consisting of the document's owner/version/side
footer. These strings are what the **citation chips display**: **answers correct, citations
misleading.** Bears on **A29's PDF caveat** (now with evidence against it). **A29's status is
unchanged; `SPEC.md` is not edited; no criterion is added.**

**Metric evidence (Tier 1 under-count, §19.6):** all **15 returned NON-EMPTY sources**, so the
run logs **15 answered / 0 refused** by the Tier 1 signal **despite one actual refusal** — a live
demonstration of the documented under-count.

**Also recorded:**
- The **mojibake** in the results file (accented names, em dashes) came from a **PowerShell
  `Out-File` redirect, NOT the database** — earlier terminal output rendered the same strings
  correctly. **No data issue; do not chase it.**
- **PC-14** (SOP owner/version/date) passed from the **document title-block chunk**. It is a
  **weak case** — title-block chunks rank highly for almost any question, so it can barely fail.
  **Low-value evidence.**

### 2026-09-15 — March 2026 date GROUNDED (enquiry closed); PDF chunk titles/bodies MISALIGNED; deferred ingestion bundle consolidated
**March 2026 date — grounded, not fabricated. ENQUIRY CLOSED.** An API answer stated the escalation
thresholds came from a desk-head agreement "confirmed in March 2026". Read-only chunk inspection
confirms the date **IS in the corpus**, in **three of the five** chunks retrieved for that answer:
`1658a960c58940fa9ed2a738f7af00d3` (SOP, "Step 6") — "most recently March 2026";
`9253c4581ee44b21806eac1a2f435511` (xlsx, "Escalation Rule") — "confirmed by Priya Raman", and
separately "Last changed March 2026"; `a2789969e0b849c697416f29029181a5` (SOP, "On the escalation
threshold"). **No fabrication occurred.** This line of enquiry is closed.

**MINOR OBSERVATION (record only — do not act):** the documents say the thresholds were last
**CHANGED** in March 2026 and were **CONFIRMED** by Priya Raman with **no date**. The answer merged
these into "confirmed in March 2026" — a claim neither document makes. **Compression, not
invention**, but the xlsx also says "reconfirm quarterly", so changed-vs-confirmed is a real
distinction. Low severity, one instance, no fix proposed.

**NEW FINDING — PDF chunk titles and bodies are MISALIGNED** (more serious than the earlier "PDF
section titles are wrong"). In `NBCA_Quick_Reference_Card.pdf`:
- Chunk `d740a2f1fc82499abccd19e36f3fc2a4` has `section_title` beginning "6 Apply the escalation
  rule: >$10k AND >5 days AND not fast-close", but its **TEXT is only** "row. Reading the scanned
  claim advice".
- The actual escalation sentence lives in a **DIFFERENT** chunk,
  `29b4dc3fd7c2493799d4c9866bc41ae5`, mislabelled "CLAIM_NO_MATCHING_BREAK".
So PDF chunks carry **other chunks' headings**. Consequence: a **citation chip can point a user at
a chunk that does not contain the cited content** — the citation is **not merely ugly, it is
wrong**. The PDF case in the positive set (**PC-11**) **passed with a citation pointing at a chunk
lacking the answer**. **This raises the priority of the PDF fix within the deferred ingestion
bundle. No investigation, no fix proposed, A29/`SPEC.md` untouched.**

**CONSOLIDATED DEFERRED INGESTION BUNDLE** (record only — **nothing is approved to build**). All
four must travel in **ONE re-ingestion pass**; `GROUNDING_REGRESSION_POSITIVE.md` (**14 of 15
passing**; locating phrases, **not** chunk ids) is the **before/after acceptance check** for that
pass.
1. **xlsx header detection** — the `parse_xlsx` `header=0` bug, carrying the owner's two prior
   reservations.
2. **PDF heading extraction** — titles misaligned with bodies (this entry).
3. **Page-number capture** — chunks store nothing page-like, so API `sources` always return
   `page=null`.
4. **Page-footer bleed** — e.g. "Page of | Internal use" inside the SOP "Key contacts" chunk.

### 2026-09-15 — PDF misalignment mechanism identified; NEW silent-content-loss defect (all formats); revised ingestion bundle; Tier 1 verified live on the UI
**PDF HEADING MISALIGNMENT — MECHANISM IDENTIFIED.** `ingestion/parsers.py::parse_pdf` uses
`partition_pdf`'s **fast (non-layout-aware)** strategy, then `_group_unstructured_elements` walks a
**flat** element list with a **"most recent heading wins"** rule. In a two-column layout the parser
**interleaves the columns**, so a heading from the left column attaches to the next line of the
RIGHT column. **Confirmed by re-running the parser on disk: deterministic, reproducible, 23
sections identical to the stored index.** Not an off-by-one; **not** a failure to detect headings.
**Tuning `_looks_like_heading` CANNOT fix it** — the correct headings are found and then paired
with the wrong bodies. **DOCX is correct** because `partition_docx` preserves real document order
and Word heading styles; the grouping code is shared, the input quality is not. **Page furniture**
("Global Custody Operations Owner: … Side 1 of 2 …") passes the heading test and becomes a
`section_title`. **Prevalence beyond this one card is UNKNOWN and must not be generalised.**

**SEPARATE, PREVIOUSLY UNKNOWN DEFECT — SILENT CONTENT LOSS.** A **different bug** from the
misalignment above and needing its own fix. `parsers.py:242` emits a section only if
`current_texts` is non-empty, so a heading **immediately followed by another heading is DISCARDED
with its text**. It lives in `_group_unstructured_elements`, **shared by the DOCX path**. Measured
across all **13 distinct corpus files** (read-only re-parse, no re-ingestion):

```
file                                    type  headings sections dropped
AML_Escalation_Procedure.docx           docx      6       7       0
AML_Policy.pdf                          pdf       6       5       1
AML_Thresholds.xlsx                     xlsx      0       1       0
HR_Approval_Matrix.xlsx                 xlsx      0       1       0
HR_Grievance_Policy.pdf                 pdf       5       6       0
HR_Leave_Procedure.docx                 docx      6       7       0
Incident_Response_Procedure.docx        docx      6       7       0
NBCA_Daily_Operations_SOP.docx          docx     53      40      13
NBCA_Exception_Matrix_Quick_Ref.xlsx    xlsx      0       7       0
NBCA_Quick_Reference_Card.pdf           pdf      48      23      25
NBCA_Training_Onboarding_Guide.docx     docx     36      27       9
Security_Incident_Policy.pdf            pdf       6       5       1
Severity_Thresholds.xlsx                xlsx      0       1       0
```

**SEVERITY DIFFERS BY FORMAT (explicit):**
- **DOCX: LABELS lost, not content.** The 13 and 9 drops are mostly TOC duplicates and container
  headings ("8. Senior notes", "9. Glossary and contacts", "2.1 Stage by stage", "3.3 Three breaks
  worth understanding in detail") whose paragraph bodies still appear under their child headings.
  Citations still show correct section names. Real but **minor**.
- **PDF (two-column card): CONTENT lost.** 25 drops, all **gone entirely**, including genuine
  content: "4 Sort by our_ref + value_date to spot duplicate pairs", "DUPLICATE_PAYMENT - same ref
  + date twice", and the whole Key contacts block (Raman, Meyer, Dubois, Baumann). **These strings
  exist in NO chunk of that file.**
- **XLSX: IMMUNE.** `parse_xlsx` sets `section_title = sheet_name` and never enters the grouping
  code.

**WHY THIS MATTERS:** a refusal is supposed to mean the documents have a gap. Where content is
dropped at ingestion, **a refusal means the PARSER has a gap, and nothing distinguishes the two on
screen.** The damage here was masked only because the lost PDF contacts are duplicated in the SOP
and the xlsx — the same redundancy effect already recorded for the image gap.

**METHODOLOGY FINDING (prominent): the synthetic corpus CANNOT detect this class of defect.** Zero
drops across all three synthetic `.docx`; one cosmetic title line per synthetic `.pdf`. The real
documents dropped **13, 9 and 25**. Step 8, the adversarial suite, `GROUNDING_REGRESSION.md` and
`tests/offline_retrieval_eval.py` all run on nine clean single-column files with **no table of
contents, no nested headings and no multi-column layouts** — shapes too simple to exhibit the bug.
The real corpus surfaced it within a day. **Argument for adding deliberately awkward documents
(TOC, nested headings, two-column, page furniture) to the synthetic corpus. Nothing approved to
build.**

**REVISED DEFERRED INGESTION BUNDLE — SUPERSEDES the four-item list above.** Record only; nothing
approved:
1. **xlsx header detection** (`parse_xlsx` `header=0`) — the owner's two reservations stand.
2. **Silent heading loss** (`parsers.py:242`) — **ALL formats** via the shared grouping code.
   Contained fix, independent of any layout work.
3. **PDF section labelling + page-number capture — MERGED.** Owner direction (2026-09-15): **STOP
   inferring PDF section titles; label PDF chunks by PAGE NUMBER instead.** A page number is a
   **checkable fact**; an inferred section title is a claim that can be wrong. The **layout-aware
   parse option is REJECTED** for the same reason OCR was: heavy native Windows dependencies. **This
   rejection is specific to a layout-aware PARSER and does NOT revive the old OCR reasoning against
   the vision-model route (F8).**
4. **Page furniture** — footer bleed inside chunk text AND running headers passing the heading
   test. Same family, one item.

All four ship in **ONE re-ingestion pass, across ALL FIVE Workspaces** (owner decision 2026-09-15),
with `GROUNDING_REGRESSION_POSITIVE.md` as the before/after acceptance check.

**TIER 1 LOGGING VERIFIED LIVE ON THE UI.** Three UI questions on 2026-09-15 wrote three correct
rows to `data/logs.db` (**log_ids 34–36**): right workspace, right model slug, `source='ui'`,
`lexical_degrade=0`, `error_type=None`, **no question or answer text**.
- Two were **refusals** and **BOTH logged `outcome='answered'`** because `chunks_retrieved=5`. Two
  more live instances of the **§19.6 under-count**, now demonstrated on the **UI** as well as the
  API.
- The HR "Severity 1" refusal was **CORRECT**: "Severity" appears in **zero chunks** of the HR
  Workspace; that content exists only in **ITSEC and All Policies**. Recorded as **Workspace
  segregation working as designed** and as a concrete illustration of **OPEN-10's cost**.
- One row showed `retrieval_ms ≈ 22,400` against ≈20 ms for the others, consistent with first-use
  **model warm-up**. Observation only — exactly the shape the **dashboard decision** anticipated
  (averages hide it, slowest-10% does not). **Do not investigate.**

---

## Rejected approaches

### 2026-09-11 — NEVER delete `data/` to "clean" before a test run
**Rejected, hard rule.** Running `Remove-Item -Recurse -Force data` (or any
deletion of the repo `data/` directory) before `pytest` destroyed the owner's
uploaded corpus + conversations **three times** across this project; the third
time was pure habit long after the cause was fixed. `data/` holds live runtime
state (the SQLite DB **and** `data/{workspace_id}/sources/` — the actual uploaded
bytes); it is gitignored, so deletion is unrecoverable. The snapshot-based
conftest guard already tolerates a pre-existing `data/` from a stopped app, so
deletion is **never** required for the suite to pass. If a clean DB is genuinely
needed, use a **temp cwd** (`monkeypatch.chdir(tmp_path)` in tests, or run the
script from a temp dir) — never touch the real `data/`. Any future agent: do not
delete `data/`, and verify ownership of a `data/` directory before touching it.

### 2026-09-13 — Image reading was rejected for the WRONG reason — supersedes the OCR entry
**Supersedes:** "OCR is scoped-and-deferred (out of scope for the PoC) — SPEC
§15.1" (Codebase discoveries, 2026-09-11). That entry rejected reading embedded
images, but its reasoning was **OCR-specific**: Tesseract and poppler native
binaries on Windows, minutes per file, file-level-only citations, and a vision
model additionally needed for DOCX. **That reasoning is void for the actual
proposal**, which needs none of it.

The real proposal is to send each **extracted image to a vision-capable model
through the SAME OpenAI-compatible endpoint already configured** (SPEC §14), and
store the returned description as text inserted at the point the image sat. No
new software, no native dependencies, no separate toolchain.

**F8** is therefore deferred **by DIRECTION, not by cost.** If the tool's value
is other systems calling it for specific answers (§17 F7), image content rarely
matters, because those answers live in text. If that direction changes, this
decision reopens.

The image-count warning in Manage → Knowledge (SPEC §15.1) remains the only
signal of the gap, and only the Owner sees it.
Authority: Answered by project owner on 2026-09-13.

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

### 2026-09-15 — CORRECTION to the mechanism entry (evidence strength); PC-01 DECIDED as correct strictness

**PART 1 — CORRECTION: evidence strength on the PDF mechanism.** This corrects the earlier entry
"2026-09-15 — PDF misalignment mechanism identified; NEW silent-content-loss defect (all formats);
revised ingestion bundle; Tier 1 verified live on the UI" (left unedited). That entry states
`parse_pdf` "uses `partition_pdf`'s fast (non-layout-aware) strategy." **That is an INFERENCE
recorded as an observation — the code does not say it.** `ingestion/parsers.py` **lines 89 and 135**
call `partition_pdf(filename=file_path)` with **no `strategy=` argument**, so `unstructured`'s
default applies. Restated at the correct strength:
- **DEMONSTRATED** (by direct re-parse on disk): the flat element list, the column interleaving,
  the resulting wrong heading/body pairings — deterministic and reproducible, **23 sections
  identical to the stored index**.
- **INFERRED, NOT DEMONSTRATED:** *which* `partition_pdf` strategy produced it. The output is
  **consistent with** a non-layout-aware parse. **Nothing more.**

Everything else in that entry stands unchanged. **Do not change the call.** *Observation only:* the
docstring at `parsers.py` line 128 describes this path as "layout-aware", which the evidence
contradicts. No code or comment change.

**PART 2 — CORRECTION: the xlsx wording.** Several entries and `state.md` describe the xlsx defect
as "`parse_xlsx` `header=0`". **The code contains no `header` argument:** `parsers.py` line 213 is
`pd.read_excel(file_path, sheet_name=None, engine="openpyxl")`, and `header=0` is **the pandas
DEFAULT.** The defect is **real and unchanged** — physical row 1 is treated as the column headings —
but anyone grepping for `header=0` will find nothing. Correct wording recorded once, here; the
earlier entries and `state.md` wording are **not** edited.

**PART 3 — PC-01 DECIDED: correct strictness, NOT a defect.** Owner decision, 2026-09-15. PC-01
("Where do escalated breaks go and who receives them?") refuses even though the answer is in the
rank-1 retrieved chunk. It is now classified as **CORRECT §18 STRICTNESS** — the open judgement call
is **resolved in the tool's favour**. It is **NOT a defect.** Reason: in the corpus the escalation
pack's destination appears only **incidentally** — a subordinate clause about an 11:00 deadline,
plus a glossary definition — whereas **all 14 passing cases state their answer as a declarative
fact**. The model distinguishing "mentioned in passing" from "specified" is close to intended §18
behaviour. It is also the **third time** the tool has pointed at the same thin spot in that SOP.
**Loosening the model's caution to paper over a weak document is the wrong trade.** Consequence:
**the fix belongs in the SOP DOCUMENT, not the system prompt** — and it must **NOT** be made until
the ingestion bundle is built and re-verified, or PC-01's meaning changes underneath us. This
**SUPERSEDES** the classification in the earlier entry "DEFECT: over-refusal on retrieved material"
(2026-09-15) — referred to by title, **not edited**. No `SPEC.md` change, no prompt change, no code.
Authority: **Answered by project owner on 2026-09-15.**

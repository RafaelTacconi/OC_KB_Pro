# Internal AI Workspace Application — Implementation Spec v3

**Status:** refinement of the existing draft (`workspace_app_poc_ui.zip` + attached design review).
**Audience:** an AI coding agent implementing changes directly against the existing codebase.
**Supersedes:** nothing. This document *adds to and corrects* the existing implementation; it does not restart it.

---

## 0. How to read this document

### 0.1 Provenance of every statement

Each requirement below is tagged so the implementing agent knows how much latitude it has:

| Tag | Meaning |
|---|---|
| `[EXISTING]` | Already implemented in the archive. Do not change unless a `[FIX]` says so. Stated here only so the agent has the full picture. |
| `[NEW]` | Requested by the project owner in the refinement brief (multi-Workspace, multi-Chat). Must be built. |
| `[FIX]` | A defect confirmed in the attached review and/or re-verified against the code. Must be fixed. |
| `[DERIVED]` | Not stated in the draft or the brief, but mechanically required to make a `[NEW]` item work (e.g. a DB migration). Low-latitude: implement as written. |
| `[OPEN]` | Genuinely unspecified. **Do not invent an answer.** Implement the stated interim behaviour if one is given, and surface the question to the project owner. |

### 0.2 A gap the agent must know about

**The original "Internal AI Workspace Application spec (v2)" is not in the archive.** The code's docstrings reference Sections 4–16 and numbered acceptance criteria (#6, #7, #9, #10) of that document, but the document itself was not provided. Everything in this spec is reconstructed from:

- the source code in `workspace_app/`,
- `README.md` inside the archive,
- the attached design review.

**Consequence:** section-number references such as "Section 8.2a, Option A" are preserved verbatim from the code because they are load-bearing comments, but they **cannot be verified** here. If any requirement in this document appears to contradict spec v2, spec v2 wins and this document should be corrected. See `[OPEN-1]`.

### 0.3 Verification performed while writing this spec

The following were established by *executing* the code in the archive, not by reading it:

- The `break`/`continue` defect in `prompting/assemble.py` reproduces exactly as the review describes — one oversized top-ranked chunk drops **all** subsequent chunks, producing an empty knowledge block. Re-confirmed independently (§7.2).
- `DELETE FROM chunks_fts WHERE rowid = ?` on the external-content FTS5 table **does** correctly remove the index entry, **provided the corresponding `chunks` row still exists at the time of deletion**. `delete_source()` gets this ordering right today. Any new cascade (e.g. Workspace deletion) must preserve it. See §7.7.
- Only three files reference `DEFAULT_WORKSPACE_ID` (`config.py`, `app.py`, `tests/offline_retrieval_eval.py`), which is why the multi-Workspace change is small (§3.1).

---

## 1. Domain vocabulary

Fixed terms. Use these names in code, UI copy, and commit messages.

| Term | Definition |
|---|---|
| **Workspace** | A named, isolated container for one body of knowledge. Owns: Sources, Instructions, Tasks, Members. Retrieval never crosses a Workspace boundary. `[EXISTING]` — now instantiable more than once `[NEW]`. |
| **Owner** | Role `owner`. Can access the Manage surface and create Workspaces. |
| **Member** | Role `member`. Chat only. Never sees Manage. |
| **Source** | One uploaded file (`pdf` / `docx` / `xlsx`) belonging to exactly one Workspace. |
| **Chunk** | A ~350–500 token slice of a Source, with an embedding of a short excerpt. |
| **Instructions** | Free-text behavioural rules stored per Workspace, injected into every prompt. |
| **Task** | A named, stored prompt (e.g. `/summarize-policy`) belonging to one Workspace, surfaced as a button above the chat box. |
| **Chat** | `[NEW]` A named conversation thread belonging to one (Workspace, user) pair. Holds an ordered list of messages. Multiple Chats may exist per Workspace per user. |
| **Message** | One user or assistant turn, belonging to exactly one Chat. |

---

## 2. Constraints carried forward from spec v2

These are quoted or paraphrased from the code's own docstrings and must continue to hold. `[EXISTING]`

1. **C3 — Ingestion boundary.** UI code calls only `ingestion.pipeline.ingest_source()` and `ingestion.pipeline.delete_source()`. It never imports a parser, chunker, or embedder. `ingestion/*` never imports Streamlit; it communicates status only through the `sources` row.
2. **C4 — One model call site.** `models/router.py::call_model(prompt, model_id) -> str` is the only function that may talk to a model provider. (The draft widened the v2 signature from `call_model(prompt)` to add `model_id`; the README flags this as a deliberate deviation still awaiting the spec owner's confirmation — see `[OPEN-2]`.)
3. **C6 — No authentication.** "Sign in" is a selectbox over the hardcoded `TEST_USERS` list. Do not build login, SSO, invites, or password handling.
4. **C7 — No live `/` autocomplete.** Tasks are a button row, not an inline slash-command parser (`st.chat_input` cannot support it).
5. **C9 — SQLite discipline.** Every connection goes through `db.get_connection()` with WAL + `busy_timeout=8000` + `foreign_keys=ON`. Transactions stay short. **Never hold a connection open across a model call or a parse.**
6. **Central prompt assembly.** `prompting/assemble.build_prompt()` is the only place a prompt string is constructed. No caller concatenates prompt fragments.
7. **`source_type = 'confluence'` is reserved and inactive.** No UI path may set it.
8. **Retrieval budget is independent of context window.** `MAX_RETRIEVED_TOKENS = 3000` is a retrieval-quality ceiling, not a hardware limit. Do not raise it because models have 256k windows. Raising it requires evidence from the offline evaluation (§9.3).

---

## 3. Assessment of the three proposed refinements

The brief asked for these to be evaluated, not just implemented. This section is the evaluation; §4 onward is the specification.

### 3.1 Multiple Workspaces per Owner — **adopt**

**Verdict: correct, and cheaper than it looks.** The data model already assumes it. Every table that holds Workspace-scoped data (`sources`, `chunks`, `tasks`, `chat_messages`, `workspace_members`) already carries a `workspace_id` foreign key, and both retrieval paths already filter on it:

- `lexical_search`: `WHERE chunks_fts MATCH ? AND chunks.workspace_id = ?`
- `semantic_search`: `WHERE chunks.workspace_id = ? AND chunks.embedding IS NOT NULL`

Uploaded files are already namespaced on disk as `data/{workspace_id}/sources/`. Streamlit session-state keys are already suffixed with `workspace_id` (`model_picker_{workspace_id}`, `selected_task_{workspace_id}`, `uploader_{workspace_id}`).

The single-Workspace assumption lives in exactly three places, none of them structural:

1. `app.py` line ~88: `workspace_id = DEFAULT_WORKSPACE_ID  # PoC: single fixed Workspace`
2. `app.py`: the string `"AML Workspace"` hardcoded in `st.set_page_config(page_title=...)` and `render_brand(...)`
3. `tests/offline_retrieval_eval.py`: `from config import DEFAULT_WORKSPACE_ID` in `__main__`

So the work is: a Workspace selector, a create-Workspace form, and threading a variable that already exists everywhere else. **No retrieval, ingestion, prompting, or model code changes at all.**

**What it costs.** Two things get worse, and the spec must handle them:
- The user now has to pick the right Workspace before asking. A question asked in the wrong Workspace produces a confident "the knowledge base doesn't cover this" — which is *correct behaviour* but reads as a failure. Mitigation in §5.2.4 (grounding visibility).
- A document relevant to two Workspaces must be uploaded, chunked, and embedded twice, and maintained in both. There is no cross-Workspace source sharing and this spec does not add one. See `[OPEN-6]`.

### 3.2 "Narrower Workspaces produce more accurate answers" — **largely correct, but the mechanism is not the one stated**

The assumption is **directionally right**, and worth acting on. But the stated reason — "the system would have a more relevant set of knowledge to work with instead of mixing unrelated topics" — implies the model sees the knowledge base. It does not.

**What actually happens per question:** `hybrid_search(..., top_k=5)` returns at most 5 chunks, capped at 3000 tokens total, and *only those* reach the model. A Workspace with 50 documents and a Workspace with 5 documents both send the model the same ~5 chunks. Corpus size does not change how much the model reads. So focus does not help by "giving the AI less to sift through" at generation time.

**Where focus genuinely helps — ranked by strength of the effect:**

**(a) Instructions and Tasks become specific — the strongest and only *guaranteed* gain.**
`workspaces.instructions` is injected into **every** prompt in that Workspace, and Tasks are per-Workspace. With one mixed Workspace, the Instructions must be generic enough to be harmless across all topics, and the Task row accumulates buttons for unrelated jobs. With three focused Workspaces, each gets Instructions written for one domain (terminology, required output shape, escalation rules, what "cite the source" means for that corpus) and a short, relevant Task list. This is a deterministic quality improvement, not a probabilistic one — it does not depend on retrieval behaving well.

**(b) Precision@5 improves — real, and this codebase is unusually exposed to it.**
Recall is not the issue: `semantic_search` is brute-force cosine over *every* chunk in the Workspace, so the correct chunk is always scored. The risk is that it fails to *rank* in the top 5 because distractors from unrelated topics outrank it. Two properties of the current implementation amplify that risk:

- **The lexical query is an OR of every token, unquoted for stopwords.** `_sanitize_fts_query()` turns "what is the policy for escalation" into `"what" OR "is" OR "the" OR "policy" OR "for" OR "escalation"`. Any chunk in the Workspace containing "the" is a candidate. The larger and more varied the corpus, the more junk enters the lexical candidate pool, and RRF then awards those candidates rank credit. Segregation directly shrinks this pool.
- **Cross-domain vocabulary collisions.** Words like *escalation*, *threshold*, *review*, *approval*, *deviation* carry different meanings in an AML corpus versus an HR or procurement corpus. Both the Porter-stemmed lexical index and a 384-dimension MiniLM embedding are poor at disambiguating those. Two topically distant bodies of text sharing procedural vocabulary is close to the worst case for this retrieval stack — and exactly the case Workspace segregation removes.

**(c) Minor: latency.** `semantic_search` loads and scores every embedding in the Workspace on every question. Halving the corpus roughly halves that work. Immaterial at PoC scale; noted so it is not mistaken for a primary benefit.

**Where the assumption fails or backfires — the agent should not treat focus as free:**

- **Cross-cutting questions become unanswerable.** A question spanning two Workspaces cannot be answered in either. The retrieval system had a chance before; now it structurally does not. Whether this matters depends entirely on the real corpora — untestable from here.
- **Over-segmentation.** A Workspace with two documents can produce near-duplicate chunks competing for the same 5 slots, and RRF has little signal to work with. There is no evidence in the draft about a minimum viable Workspace size.
- **Routing burden moves to the user.** Accuracy measured end-to-end (did the user get a right answer?) can *fall* if users pick the wrong Workspace, even as accuracy measured per-Workspace rises.

**Implication for the project:** the assumption is sound enough to build on, and the build cost is low (§3.1), so proceed. But it is a hypothesis with a measurement path already sitting in the repo, and it should be measured rather than assumed. See §9.3 for the concrete protocol using `tests/offline_retrieval_eval.py`.

**Explicitly out of scope:** this assessment is **not** a reason to change `top_k`, `MAX_RETRIEVED_TOKENS`, `candidate_pool`, `rrf_k`, or chunk size. Constraint 8 (§2) still holds.

### 3.3 Multiple Chats per Workspace — **adopt, but the stated rationale does not apply to the current build**

**Verdict: the feature is right; the context-window justification is not currently true, and the agent must not build as though it were.**

The review already flagged the absence of any "new chat" affordance as a gap: history is loaded per `(workspace_id, user_id)` with no way to reset, archive, or delete, and grows forever. Multiple Chats fixes that.

**However — verified by reading `ui/chat_view.py::_answer()` and `prompting/assemble.py::build_prompt()`: conversation history is never sent to the model.** `build_prompt()` accepts exactly `workspace_instructions`, `retrieved_chunks`, `user_input`, `task_prompt`, `model_id`. Prior turns are stored in `chat_messages` and rendered in the UI, but they never enter the prompt. Every turn today is fully stateless.

Two consequences:

1. **The 256k context window is nowhere near being consumed, and cannot be by a long conversation.** A prompt today is roughly: system policy + Instructions + optional Task prompt + ≤3000 tokens of knowledge + the user's input. That is low single-digit thousands of tokens, no matter how many turns precede it. A 500-turn Chat costs exactly the same per call as turn 1. So "a user should not have to keep extending one conversation indefinitely because of the context limit" describes a problem this build does not currently have.
2. **"A fresh conversational context" is, today, trivially satisfied by every message.** There is no conversational context to reset.

This makes the real question a **product decision the draft never took**, and the agent must not take it silently:

> **Does a Chat's prior turns belong in the prompt?**

- **Option A — Chat is organizational only (no history in the prompt).** Faithful to the current build and to the fixed assembly order the code attributes to Section 9.1. Chats become named, separable threads: topic hygiene, a clean slate in the UI, no unbounded scroll. Follow-ups like "and what about the second one?" continue to fail, because they already do.
- **Option B — Chat carries real conversational context (history in the prompt).** Makes the brief's rationale literally true and makes follow-up questions work. But it changes the prompt assembly order (a v2 constraint), needs its own token budget, needs a decision on whether the *retrieval* query incorporates history, and reintroduces a genuine reason to start fresh Chats.

**This is `[OPEN-3]` and it is the single most consequential open question in this document.** Everything else in the Chat feature is identical under both options. §6 specifies Option A as the interim build (it is the faithful reading of the existing draft) and specifies Option B completely as a conditional extension, so switching is a contained change.

---

## 4. Target data model

Full target schema. Everything not marked `[NEW]`/`[DERIVED]` is unchanged from `db.py` and must be left alone.

### 4.1 Unchanged tables

`users`, `workspaces`, `workspace_members`, `sources`, `chunks`, `chunks_fts`, `tasks` — exactly as in the current `db.py::SCHEMA`. `[EXISTING]`

Note: `workspaces` already has `owner_user_id`, so "which Workspaces does this Owner own" is already answerable. No schema change is needed for multi-Workspace.

### 4.2 New table: `chats` `[NEW]`

```sql
CREATE TABLE IF NOT EXISTS chats (
    chat_id       TEXT PRIMARY KEY,
    workspace_id  TEXT NOT NULL REFERENCES workspaces(workspace_id),
    user_id       TEXT NOT NULL REFERENCES users(user_id),
    title         TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
```

- A Chat belongs to exactly one Workspace and one user. Chats are **not** shared between users; this mirrors the existing per-user history behaviour (`_load_history` already filters on `user_id`). `[DERIVED]`
- `updated_at` is set to the timestamp of the most recent message in the Chat, so the Chat list can be ordered most-recent-first.

### 4.3 Changed table: `chat_messages` `[NEW]`

Add one column:

```sql
chat_id  TEXT REFERENCES chats(chat_id)
```

- Declared **nullable at the SQL level** because `ALTER TABLE ... ADD COLUMN NOT NULL` without a default is not permitted, and legacy rows exist. `[DERIVED]`
- **Enforced non-null in application code**: every write path must supply a `chat_id`. Any row with `chat_id IS NULL` after migration is a bug.
- `workspace_id` and `user_id` stay on `chat_messages` even though they are now derivable through `chats`. Denormalised, but every existing query and the Manage-view counts rely on them. Do not remove them.

### 4.4 Indexes `[DERIVED]`

Currently the schema has no indexes beyond primary keys. With N Workspaces and N Chats, several hot queries become full scans. Add:

```sql
CREATE INDEX IF NOT EXISTS idx_chunks_workspace   ON chunks(workspace_id);
CREATE INDEX IF NOT EXISTS idx_sources_workspace  ON sources(workspace_id);
CREATE INDEX IF NOT EXISTS idx_tasks_workspace    ON tasks(workspace_id);
CREATE INDEX IF NOT EXISTS idx_chats_ws_user      ON chats(workspace_id, user_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_messages_chat      ON chat_messages(chat_id, created_at);
```

These are additive and behaviour-neutral.

### 4.5 Migration `[DERIVED]`

`db.init_db()` uses `CREATE TABLE IF NOT EXISTS`, so an existing `data/workspace_app.db` will **not** pick up the new column. Add an idempotent `db.migrate_db()`, called from `config.bootstrap()` immediately after `init_db()`:

1. `PRAGMA table_info(chat_messages)` → if `chat_id` absent, `ALTER TABLE chat_messages ADD COLUMN chat_id TEXT REFERENCES chats(chat_id);`
2. Backfill: for each distinct `(workspace_id, user_id)` in `chat_messages` where `chat_id IS NULL`, create one `chats` row titled `Imported conversation`, with `created_at` = earliest message timestamp and `updated_at` = latest, then `UPDATE chat_messages SET chat_id = ? WHERE workspace_id = ? AND user_id = ? AND chat_id IS NULL`.
3. Create the indexes in §4.4.

The migration must be safe to run against a fresh empty DB and safe to run repeatedly.

---

## 5. Multi-Workspace requirements

### 5.1 Seeding `[EXISTING, adjusted]`

`config.bootstrap()` remains idempotent and keeps creating the one example Workspace (`aml-workspace` / "AML Workspace") with its two seed Tasks and all `TEST_USERS` as members. Do not remove this — the offline evaluation harness and first-run experience depend on a Workspace existing.

Rename nothing in `config.py`. `DEFAULT_WORKSPACE_ID` retains its current meaning: *the seeded example Workspace*, not *the only Workspace*. Update its comment to say so.

### 5.2 UI

#### 5.2.1 Workspace switcher (sidebar) `[NEW]`

Rendered in `app.py`, below the user selectbox and above primary navigation.

- A `st.selectbox` listing the Workspaces visible to the current user (§5.3), labelled by `workspaces.name`, ordered by `name`.
- Selection persists in `st.session_state["wa_workspace_id"]`.
- On startup, or if the stored id is no longer visible to the current user, default to the first Workspace in the list.
- **Switching Workspace must clear:** `selected_task_{old_workspace_id}` and the active Chat selection (`wa_chat_id`), then `st.rerun()`. Model-picker state is already per-Workspace keyed and may persist.
- **Switching user must re-evaluate visibility.** A user switch that leaves the current Workspace invisible falls back to the first visible one.

#### 5.2.2 Creating a Workspace (Owner only) `[NEW]`

- An expander in the sidebar, `+ New Workspace`, visible only when `current_user["role"] == "owner"`.
- Form fields: **Name** (required, free text) and **Instructions** (optional, `st.text_area`). Nothing else. Do not add description, icon, colour, tags, or visibility settings — none are in the draft or the brief.
- On submit: insert into `workspaces` with `workspace_id = uuid.uuid4().hex`, `owner_user_id = current_user["user_id"]`, `created_at = updated_at = now`, then insert `workspace_members` rows per §5.3, then set `wa_workspace_id` to the new id and `st.rerun()`.
- **Name uniqueness is not enforced** (`workspaces.name` has no unique constraint today and Tasks have the same looseness). Two Workspaces may share a name. This is a real usability hazard with a name-labelled selectbox — see `[OPEN-5]`.
- Empty/whitespace-only names are rejected with an inline message; do not create the row.

#### 5.2.3 Branding `[FIX]`

`app.py` currently hardcodes `"AML Workspace"` in `st.set_page_config(page_title=...)` and `render_brand(...)`. With multiple Workspaces this becomes actively wrong.

- `render_brand()` must be called with the **current Workspace's** `name` from the DB.
- `st.set_page_config()` runs before a Workspace is known, so its `page_title` must become a **product-level constant**, not a Workspace name. Use a neutral constant (e.g. `APP_TITLE = "AI Workspace"`) defined in `config.py` and imported. Do not attempt to make the browser tab title track the selected Workspace.
- `render_chat_view` and `render_owner_view` already read the Workspace name from the DB via `_load_workspace()`. Leave that as is.

#### 5.2.4 Grounding visibility for Members `[FIX]`

Flagged in the review; multi-Workspace makes it materially worse, because a Member can now be sitting in an empty or wrong Workspace with no signal.

In the chat view header area, for **all** users, render a one-line status derived from a single count query:

- `0` indexed Sources → a visible warning: this Workspace has no knowledge yet, so answers will not be grounded in any document.
- `>0` indexed Sources → a neutral caption stating how many Sources are indexed.
- Any Sources in `failed` state → for Owners only, a note pointing at Manage → Knowledge. Members do not need the failure detail.

Use the existing pill/caption components (`ui/pills.py`, `ui/cards.py`). Do not invent a new visual language.

### 5.3 Membership on new Workspaces `[OPEN-4]` — interim behaviour specified

The draft never states who can access a newly created Workspace. `seed_default_workspace()` adds **every** entry in `TEST_USERS` as a member.

**Interim rule (implement this):** on Workspace creation, insert a `workspace_members` row for **every user in `TEST_USERS`**, exactly mirroring the seed behaviour. This is an extension of existing behaviour rather than a new access-control mechanism, and it keeps constraint C6 intact (no invite/removal UI is added).

**Consequence to surface to the project owner:** under this rule an Owner cannot create a private Workspace. If per-Workspace access control is wanted, that is a new requirement requiring an invite/removal mechanism in the Manage → Users section, which is currently read-only by design. Do not build it without an explicit decision.

Regardless of the rule chosen, the Workspace list shown to a user **must** be derived from `workspace_members`, not from `workspaces` directly, so that access control is enforced in one place if the rule later changes:

```sql
SELECT w.* FROM workspaces w
JOIN workspace_members wm ON wm.workspace_id = w.workspace_id
WHERE wm.user_id = ?
ORDER BY w.name;
```

### 5.4 Manage view `[EXISTING]`

`render_owner_view(workspace_id)` already takes the Workspace as a parameter and scopes every query to it. It needs **no changes** for multi-Workspace beyond receiving the selected id instead of the constant.

Do **not** add a "Workspaces" section to the Manage rail. Manage is per-Workspace by construction; Workspace creation and switching live in the sidebar, one level above it.

### 5.5 Rename and delete `[OPEN-6]` — do not build without a decision

Neither the draft nor the brief mentions renaming or deleting a Workspace. Once Owners can create Workspaces freely, the absence of both becomes noticeable, but building them is a new requirement, not a refinement.

If approved, a Workspace delete **must** cascade in this order inside one transaction, or FTS index corruption and orphaned rows will result:

1. For every `chunk` in the Workspace: `DELETE FROM chunks_fts WHERE rowid = ?` — **before** deleting the `chunks` rows (verified: external-content FTS5 deletion requires the content row to still be present).
2. `DELETE FROM chunks WHERE workspace_id = ?`
3. `DELETE FROM sources WHERE workspace_id = ?`
4. `DELETE FROM chat_messages WHERE workspace_id = ?`
5. `DELETE FROM chats WHERE workspace_id = ?`
6. `DELETE FROM tasks WHERE workspace_id = ?`
7. `DELETE FROM workspace_members WHERE workspace_id = ?`
8. `DELETE FROM workspaces WHERE workspace_id = ?`
9. Outside the transaction: remove `data/{workspace_id}/`.

Plus: a typed confirmation (§7.4), a defined behaviour when the last Workspace is deleted, and a rule for what happens to users currently viewing it. All unspecified. **Not in scope until answered.**

---

## 6. Multi-Chat requirements

### 6.1 Model

- A Chat belongs to one Workspace and one user (§4.2).
- A user may have any number of Chats per Workspace.
- Messages belong to exactly one Chat.
- **Chats do not change retrieval.** `hybrid_search(query, workspace_id, top_k=5)` is unchanged and still scopes to the Workspace. A Chat never narrows or widens the knowledge available.

### 6.2 Chat lifecycle `[NEW]`

**Selecting.** `st.session_state["wa_chat_id"]` holds the active Chat. On entering a Workspace, default to that user's most recently updated Chat in that Workspace; if none exists, no Chat is active and the view shows the empty state.

**Creating.** A `+ New chat` button in the chat view. Two acceptable implementations — pick the first:

- **Lazy (preferred):** clicking `+ New chat` sets `wa_chat_id = None` and shows an empty conversation. The `chats` row is inserted on the **first message**, inside the same flow that persists that message. This avoids accumulating empty Chat rows from stray clicks.
- Eager insert on click is acceptable if lazy proves awkward in Streamlit's rerun model, but then an empty-Chat cleanup is required.

**Titling `[DERIVED]`.** A Chat needs a label in the list. Interim rule: on the first user message in a Chat, set `title` to that message's text truncated to 60 characters (single line, trailing whitespace stripped, `…` appended if truncated). Until then, display `New chat`. **The draft specifies nothing here** — alternatives are a plain counter ("Chat 3"), a user-editable title, or a model-generated summary title (which would cost an extra model call). See `[OPEN-7]`.

**Listing.** In the chat view, above the conversation: the active Chat's title plus a control to switch Chats — a `st.selectbox` over the user's Chats in this Workspace, ordered by `updated_at` descending, alongside the `+ New chat` button. Do not build a full sidebar chat drawer; nothing in the draft asks for one and the sidebar already carries user, Workspace, and navigation.

**Renaming and deleting Chats:** `[OPEN-8]` — not specified. Do not build. If deletion is added later it must delete the Chat's `chat_messages` rows first, then the `chats` row, behind the confirmation pattern in §7.4.

### 6.3 History loading `[NEW]` — replaces existing behaviour

`ui/chat_view.py::_load_history(workspace_id, user_id)` becomes `_load_history(chat_id)`:

```sql
SELECT * FROM chat_messages WHERE chat_id = ? ORDER BY created_at;
```

The old `(workspace_id, user_id)` query must be removed, not kept as a fallback — leaving it would merge every Chat back into one view.

### 6.4 Writing messages `[NEW]`

`_save_message()` gains a required `chat_id` parameter and writes it. Every call site supplies it. After each write, update the parent Chat's `updated_at`.

### 6.5 Prompt context — interim Option A `[OPEN-3]`

**Build Option A.** `build_prompt()` keeps its current signature and assembly order. Prior turns in a Chat are **not** sent to the model. Under Option A a Chat is a persistent, separable thread in the UI; it does not give the model memory.

**UI honesty requirement:** the chat view must not imply memory it does not have. Do not label the feature in a way that promises the assistant remembers earlier turns. A short caption stating that each question is answered independently from the Workspace's knowledge is appropriate. Do not over-explain.

**Option B, if and only if `[OPEN-3]` is decided that way.** The full delta, so the decision can be costed:

1. `build_prompt()` gains `conversation_history: list[dict] | None = None`.
2. A new position in the assembly order must be agreed — it is a change to the v2 fixed order and cannot be chosen unilaterally.
3. A new constant `MAX_HISTORY_TOKENS` in `models/context_budget.py`, with a documented rationale in the same style as `MAX_RETRIEVED_TOKENS`. Truncation must be **oldest-first**, keeping the most recent turns.
4. A decision on whether the *retrieval* query includes prior turns. Currently `retrieval_query = user_input` (or `f"{task['name']} {user_input}"`). Changing it changes retrieval behaviour and invalidates any offline evaluation run before the change.
5. `fits_in_context()` continues to guard the total.

Under Option B, the brief's original rationale becomes real: history accumulates, and starting a new Chat becomes the correct way to reclaim budget.

---

## 7. Defects to fix

Ordered by severity. Items 7.1 and 7.2 are **blocking** — the app is not usable by test users until both are fixed.

### 7.1 `[FIX-BLOCKING]` Chat turn has no error handling and destroys user input

**Where:** `ui/chat_view.py::_answer()`.

**Current behaviour:** no `try`/`except` anywhere in the chain. `_save_message()` for the user's own question is called **after** `call_model()` returns. `models/router.py::_call_internal_gateway()` raises `NotImplementedError` unconditionally (by design — it is a placeholder), so today *every* send crashes to Streamlit's exception page and the user's typed question is never persisted.

This is structural, not a stub artifact: once a real endpoint is wired in, any timeout, rate limit, or network blip reproduces it exactly.

**Required behaviour:**

1. **Persist the user's message first**, in its own short transaction, before retrieval or the model call. Create the `chats` row here too if the Chat is new (§6.2). The user's input must survive any downstream failure.
2. Wrap retrieval, prompt assembly, and the model call in `try`/`except Exception`.
3. On failure: render an inline error inside the assistant message slot — a short human-readable message plus the exception text in a collapsed `st.expander`. Do **not** let the exception reach Streamlit's error screen. Do **not** persist an assistant message containing the error text (it would pollute the Chat and, under Option B, the model's own context).
4. Provide a **Retry** control that re-runs the same turn from the already-persisted user message. Retry must not duplicate the user message.
5. Persist the assistant message only on success, with `cited_sources`, `retrieved_chunk_ids`, `task_id`, and `model_id` as today.

Both entry points — the free-text `st.chat_input` path and the Task form's `Run task` path — go through `_answer()` and are covered by the same fix.

### 7.2 `[FIX-BLOCKING]` `build_prompt()` drops all remaining chunks after the first oversized one

**Where:** `prompting/assemble.py`, the retrieved-chunk loop.

```python
if token_count + chunk_tokens > MAX_RETRIEVED_TOKENS:
    break        # must be: continue
```

`break` abandons the whole loop the first time any chunk would overflow the budget, discarding every lower-ranked chunk — including small, highly relevant ones.

**Re-verified by execution** for this spec: with a synthetic top-ranked oversized chunk (5200 tokens, simulating the accepted "one XLSX sheet → one oversized chunk" behaviour documented in `ingestion/chunking.py`) followed by two 10-token relevant chunks, the assembled prompt contained **none** of the three. The knowledge block was empty and the model would have been asked to answer with zero grounding.

**Fix:** change `break` to `continue` so an over-budget chunk is skipped and smaller lower-ranked chunks are still considered.

**Required test** (the existing `test_build_prompt_respects_token_budget` uses two equally-sized chunks and cannot catch this): assert that given `[oversized, small_relevant_a, small_relevant_b]`, both small chunks appear in the output and the oversized one does not.

**Do not** "fix" this by splitting oversized chunks in `ingestion/chunking.py`. That behaviour is explicitly accepted in the draft and pinned by an existing unit test; changing it requires evidence from the offline evaluation.

### 7.3 `[FIX]` `hybrid_search()` has no degrade path

**Where:** `retrieval/hybrid_search.py::hybrid_search()`.

`semantic_search()` calls `_get_embedding_model()`, which lazily downloads/loads `all-MiniLM-L6-v2`. If that fails (no network to huggingface.co — the README confirms this happened in the sandbox), the exception propagates and kills the entire chat turn, even though lexical search alone would have returned usable results.

**Fix:** inside `hybrid_search()`, wrap the `semantic_search()` call in `try`/`except Exception`. On failure, proceed with lexical results only and signal the degradation to the caller so the UI can show a visible note that semantic retrieval is unavailable and results may be less complete.

**Do not silently swallow it.** Degrading without telling anyone converts a loud failure into quietly worse answers. Communicate it through a return value or a documented exception-free signal — not by importing Streamlit into `retrieval/` (constraint C3's spirit: retrieval code stays UI-free).

If lexical search *also* fails, that exception should surface to `_answer()`'s handler (§7.1).

### 7.4 `[FIX]` No confirmation on destructive actions

Source deletion (`ui/owner_view.py`, `Delete` button) and Task deletion (`Delete task` form button) are single-click and irreversible. Source deletion additionally discards embeddings that cost real compute.

**Fix:** a two-step confirm. First click sets a session-state flag keyed by the entity id and re-renders that row with an explicit `Confirm delete` / `Cancel` pair naming the item. Only the confirm click performs the deletion. Use the same pattern for both; do not build two different confirmation styles.

### 7.5 `[FIX]` Model attribution never displayed

`chat_messages.model_id` is stored for every assistant message and never rendered — odd, given that model choice is the feature it supports.

**Fix:** in the chat history renderer, for assistant messages with a non-null `model_id`, display the model's `display_name` (via `models.registry.get_model_spec`) as a small caption or pill alongside the existing citation chips. Handle an unknown `model_id` gracefully — `get_model_spec()` raises `ValueError` for ids no longer in the registry, and historical rows can outlive registry entries.

### 7.6 `[FIX]` Stale task selection sends an untagged message

If a user selects a Task (highlighting the button and revealing its form) but then types into the free-text `st.chat_input` instead, the message is sent with `task=None` while the Task chip still appears selected. Nothing tells the user the Task prompt was not applied.

**Fix:** when a Task is selected and the user submits via the free-text input, either (a) clear the Task selection and note inline that the Task was not applied, or (b) disable/annotate the free-text input while a Task is active. Choose one and apply it consistently. **(a) is preferred** — it does not block a legitimate action.

### 7.7 `[FIX]` FTS deletion ordering must be preserved and documented

`ingestion/pipeline.py::delete_source()` deletes `chunks_fts` rows **before** the `chunks` rows. Verified: this order is required — external-content FTS5 deletion reads the content row to remove the correct index terms, so deleting `chunks` first silently corrupts the index.

**Fix:** add an explicit comment at that site stating the ordering requirement, so a future Workspace-delete or bulk-delete implementation does not reverse it.

### 7.8 `[FIX]` Documentation and duplication cleanup

Low risk, low effort. All confirmed in the review; re-confirmed against the code.

| Item | Location | Action |
|---|---|---|
| `estimate_tokens` duplicated verbatim | `ingestion/chunking.py`, `models/context_budget.py` | Define once and import. Both use `len(text.split()) * 1.3`. Keep the constant `WORDS_TO_TOKENS` with it. |
| `ROLE_PILL_MAP` duplicated | `app.py`, `ui/owner_view.py` | Move to one place (`ui/pills.py` is the natural home) and import. |
| Docstring points at a non-existent module | `models/registry.py` references `ui/model_picker.py` | The picker lives in `ui/chat_view.py::_render_model_picker`. Correct the reference. |
| Missing referenced file | `.streamlit/config.toml` references `static/fonts/README.md`; `static/fonts/` is empty/absent | Either create the file or remove the reference. Do not add font binaries. |
| Brittle alignment hack | `ui/chat_view.py`, `margin-top: 1.6rem` inline style on the model note | Replace with a layout that does not depend on a fixed pixel offset (the column already uses `vertical_alignment="center"`). |
| `st.success()` immediately followed by `st.rerun()` | `ui/owner_view.py`, Save instructions and Task create/edit | The rerun discards the toast before it is seen. Either drop the `st.success` or set a session-state flag and render the confirmation after the rerun. |
| Raw exception text shown to Owner | `ui/owner_view.py`, `sources.error_message` display | Prefix with a short human-readable explanation; keep the raw text available but secondary. |

### 7.9 `[OPEN-9]` Known limitations — flagged, no fix specified

These are real but the draft accepts them or is silent. **Do not fix without a decision** — each has a cost or a behaviour change attached.

- **No stopword filtering in `_sanitize_fts_query()`.** Every token, including "the"/"is"/"for", becomes an OR term. Adding a stopword list changes retrieval behaviour and invalidates prior evaluation runs. §3.2(b) explains why this matters more with multiple/larger Workspaces.
- **Duplicate Task names allowed.** Two identically labelled buttons with no way to distinguish them. Same looseness now applies to Workspace names (§5.2.2).
- **Unicode glyph icons.** `\u25a4` (citation chip) in particular may render as a missing-glyph box on some OS/browser combinations. Needs a real device test, not a code change.
- **Small type sizes.** Several label/eyebrow styles at `0.68rem`/`0.72rem` (~11px) are borderline; needs an accessibility checker pass.
- **No responsive breakpoints.** The Task button row (`st.columns(n)`, n = number of Tasks) and the Manage rail/content `[1, 4]` split are untested on narrow viewports.
- **No caching on read helpers.** No `st.cache_data`/`st.cache_resource` on `_load_workspace`, `_load_tasks`, `_load_history`, `_load_sources`, `_load_members`. Every widget interaction re-issues several queries. Fine at PoC scale; note that adding caching interacts badly with write-then-rerun flows and needs care.
- **No response streaming.** The full answer arrives behind a blocking spinner.

### 7.10 `[FIX]` Section titles came from body-text fragments, not headings

**Where:** `ingestion/parsers.py::_group_unstructured_elements()` (shared by PDF and DOCX).

**Current behaviour:** section titles were taken from any `unstructured` element whose type was `Title`/`Header`. On real documents `partition_pdf` labels wrapped body sentences as `Title` ("Financial Crime Oversight Committee.", "channel for Severity 1.", "than 15 minutes."), while the genuine numbered headings arrive as `ListItem` ("1. Scope", "2. Escalation Timeline"). So the provenance trail showed sentence fragments instead of headings.

**Fix:** classify headings by SHAPE, not element type. A numbered-heading pattern (`^\d+(?:\.\d+)*[.)]?\s+\S`) is a heading whatever its element type; a `Title`/`Header` is a heading only if it is short, does not end with a sentence period, and starts with an uppercase letter or digit. Body fragments become body text.

**Known limitation:** this is a heuristic; it is **unvalidated against real back-office documents** (validated only against the test corpus). See `memory.md`. Re-check before citations are trusted.

### 7.11 `[FIX]` Citation chips claimed to be the model's citations

**Where:** `ui/chat_view.py` (history render) + `ui/cards.py::source_chips()`.

**Current behaviour:** the chip row under an answer rendered all retrieved chunks as if they were the model's inline citations; a one-chunk answer showed five chips.

**Fix:** the row is labelled **"Retrieved from"** and presented as the RETRIEVED set. It is not the model's inline citations. (Populating from the model's free-text citations was rejected as fragile.)

### 7.12 `[FIX]` Duplicate citation chips

**Where:** `ui/cards.py::source_chips()`.

**Current behaviour:** two retrieved chunks from the same document section produced two identical chips.

**Fix:** dedupe chips by `(display_name, section_title)`.

### 7.13 `[FIX]` Spinner disappeared before the answer arrived

**Where:** `ui/chat_view.py::_answer()` / `_retry()`.

**Current behaviour:** `st.spinner` wrapped only the model call; when it returned, the spinner closed and the answer appeared only after the caller's `st.rerun()` — a silent gap that looked like a failed send.

**Fix:** render the turn inline — the spinner sits INSIDE the assistant `st.chat_message` bubble and the answer is written into that same bubble, so the spinner transitions directly into the answer; the caller's rerun then re-renders the identical turn from the DB.

### 7.14 `[FIX]` A new Chat loses its selection after the first question

**Where:** `ui/chat_view.py::_render_chat_row()` + `_answer()`.

**Current behaviour:** the chat selector is a keyed widget whose key carries a generation counter (`wa_chat_gen`). For a brand-new chat `wa_chat_id` is `None`, so the selector renders with the `NEW_CHAT` sentinel selected and Streamlit stores `NEW_CHAT` against that key. `_answer()` then creates the chat row and sets `wa_chat_id` to the real id — but does **not** bump the generation. On the next rerun the key is unchanged, so Streamlit restores the stored `NEW_CHAT` value, overriding `index=`. Thus `chosen == NEW_CHAT` while `current == the real chat_id`, the "chosen != current" branch fires, `wa_chat_id` is reset to `None`, the generation is bumped, and it reruns into an empty new chat. The conversation appears to vanish until a manual refresh (nothing is actually lost — it is a display bug).

**Fix:** bump `wa_chat_gen` whenever a turn **creates** a Chat (i.e. `chat_id` was `None`), so the selector re-initialises from `index=` (the new real chat_id) on the next render. After the first question the chat stays selected, its title updates to the question, and the question + answer remain on screen with no refresh. Manual switching and "+ New chat" are unaffected.

**Required behaviour (A36):** after the first question in a new Chat, the Chat remains selected, its title updates to the question, and the question and answer remain visible without a refresh; switching Chats by hand and "+ New chat" still work.

---

## 8. Architecture rules for the implementing agent

These are the boundaries that make the existing codebase maintainable. Preserve them.

1. **`ui/` never imports** a parser, chunker, embedder, or provider SDK. It calls `ingest_source`, `delete_source`, `hybrid_search`, `build_prompt`, `call_model`, and `db` helpers only.
2. **`ingestion/`, `retrieval/`, `prompting/`, `models/` never import Streamlit.**
3. **One public entry point per package**, as documented in each package's docstring. New functionality goes behind the existing entry point, not alongside it.
4. **All prompt text is built in `prompting/assemble.py`.** No exceptions, including error messages destined for the model.
5. **All DB connections via `db.get_connection()`** — never `sqlite3.connect()` directly. All writes via `db.transaction()`.
6. **No network call or file parse inside a `with transaction()` block.**
7. **New constants live with their subject** — model metadata in `models/registry.py`, token budgets in `models/context_budget.py`, seed data in `config.py`. Do not scatter magic numbers into `ui/`.
8. **Maintain the project journal** — `memory.md`, `state.md`, `changelog.md` at the repository root. Not optional, not a documentation afterthought: they are how decisions survive a context window. See §13.

---

## 9. Build order

Sequenced so each step is independently verifiable and nothing is blocked on an `[OPEN]` item.

**Every step begins and ends with a journal update (§13).** Update `state.md` before starting a step; write a `changelog.md` entry, refresh `state.md`, and record the test result when finishing it. A step with no changelog entry is not done.

**Step 1 — unblock the app.** Fix 7.2 (`break` → `continue`, plus its test) and 7.1 (error handling and message persistence). After this the app fails gracefully with the stub model instead of crashing, and no user input is lost. Neither depends on any open question.

**Step 2 — resilience.** Fix 7.3 (lexical degrade path) and 7.4 (delete confirmations).

**Step 2b — Provider configuration and key expiry.** `.env.example`, `.gitignore` entry, `python-dotenv`, lazy environment reads, registry/env split, OpenAI-compatible adapter replacing the placeholder, `models/credentials.py`, sidebar warning. (Addendum A — see §14.)

Reasons to do this before Step 3 rather than after Step 7:

- It is the first point at which the application can actually answer a question. Every step so far has been verified against a stub. Steps 4–6 are UI work over the chat surface, and building them blind is worse than building them against a working loop.
- It validates Step 1's error handling against real failures — timeouts, rate limits, auth errors — rather than a synthetic `RuntimeError`.
- It touches `models/` and `app.py`'s sidebar. Step 5 also touches `app.py`'s sidebar (the Workspace switcher). Doing both in the same file across two steps is cheaper than reconciling them later.

It depends on nothing in Steps 3–7 and blocks nothing in them.

**Step 3 — schema.** Add `chats`, add `chat_messages.chat_id`, add indexes, write `migrate_db()` and wire it into `bootstrap()`. Verify against both a fresh DB and a copy of an existing one.

**Step 4 — multi-Chat.** `_load_history(chat_id)`, `chat_id` through `_save_message`, `+ New chat`, Chat selector, lazy creation and titling. Option A prompt behaviour (§6.5).

**Step 5 — multi-Workspace.** Workspace selector, create form, membership rule (§5.3), branding fix (7.3 → §5.2.3), state resets on switch.

**Step 6 — visibility.** Grounding status for all users (§5.2.4) and model attribution in history (7.5).

**Step 7 — cleanup.** 7.6, 7.7, 7.8.

**Step 8 — evaluate.** §9.3 below. This is the step that tells you whether §3.2's hypothesis holds.

### 9.3 Measuring whether Workspace focus improves accuracy

`tests/offline_retrieval_eval.py` already implements the right shape of test: per question, did the expected source appear in top-5, under lexical / semantic / hybrid.

**Change `[DERIVED]` (done):** the harness accepts `workspace_id` as a CLI argument rather than importing `DEFAULT_WORKSPACE_ID`, so it can be run per Workspace.

**Change `[NEW]` (2026-09-13):** a **second CLI argument** selects which question set runs — `aml`, `hr`, `sec`, or `all` — over three named lists `AML_QUESTIONS`, `HR_QUESTIONS`, `SEC_QUESTIONS` plus the combined `QUESTION_SET`. This lets the same harness run a focused Workspace against its own domain's questions and the mixed Workspace against all of them, without editing the file between runs. The scoring logic, `TOP_K`, and everything in `retrieval/` are unchanged. (Acceptance criterion A35.)

**Protocol to test the focus hypothesis** (requires real documents, so it cannot be run before the corpora exist):

1. Build one **mixed** Workspace containing all documents from all three intended topic areas.
2. Build three **focused** Workspaces, each with only its own topic's documents.
3. Write 10–15 real questions per topic with a known ground-truth source file, as the harness's docstring already instructs.
4. Run the harness against the mixed Workspace and against the matching focused Workspace, using the same questions.
5. Compare top-5 hit rates. A meaningful improvement in the focused runs supports the hypothesis; no difference means the benefit is limited to the Instructions/Tasks effect described in §3.2(a), which is still a real reason to segregate.

Record the results. If they are flat, that is evidence against raising `top_k` or `MAX_RETRIEVED_TOKENS` later, not for it.

---

## 10. Acceptance criteria

For the new and fixed behaviour only. The v2 acceptance criteria (#1–#10) are referenced by the code but were not supplied (§0.2) and must continue to hold.

**Multi-Workspace**

- A1. An Owner can create a Workspace with a name and optional instructions; it appears immediately in the switcher and is selected.
- A2. Uploading a Source to Workspace A never causes it to be retrieved when chatting in Workspace B. Verify at the retrieval layer, not only in the UI.
- A3. Instructions and Tasks configured in Workspace A do not appear or apply in Workspace B.
- A4. Switching Workspace clears any selected Task and any active Chat selection.
- A5. A Member sees only Workspaces they are a member of, and never reaches the Manage surface by any route.
  - **Amendment (2026-09-13) — part superseded by §17 F10.** The second half ("never reaches the Manage surface") is superseded when §17 F10 is built: under F10, Members reach Manage for Instructions, documents and Tasks; only membership management and Workspace deletion remain Owner/Admin. The first half (a Member sees only their own Workspaces) survives F10 and must be split into a criterion of its own at that point. **A5 and its test describe CURRENT behaviour, which is NOT changing in this amendment; the test must keep passing and must not be edited.**
- A6. Sidebar branding shows the currently selected Workspace's name; no Workspace name is hardcoded anywhere in `app.py`.

**Multi-Chat**

- A7. A user can start a new Chat in a Workspace; the new Chat opens empty while previous Chats remain intact and retrievable.
- A8. Messages appear only in the Chat they were sent in. Switching Chats swaps the rendered history completely.
- A9. Chats are scoped per user: user X never sees user Y's Chats, in any Workspace.
- A10. On an existing database, `migrate_db()` assigns every pre-existing message to exactly one Chat per `(workspace_id, user_id)`; no message ends up with `chat_id IS NULL`; running it twice changes nothing.
- A11. Chat lists are scoped to the current Workspace — a Chat created in Workspace A does not appear when Workspace B is selected.

**Reliability**

- A12. With `_call_internal_gateway()` still raising `NotImplementedError`, sending a message shows an inline error inside the conversation, keeps the page alive, and **persists the user's message**, which is still visible after a rerun.
- A13. Retry after a failure produces exactly one additional model attempt and does not duplicate the user's message.
- A14. Given `[oversized_chunk, small_relevant_a, small_relevant_b]`, `build_prompt()` includes both small chunks and excludes the oversized one. (This is the regression test for 7.2 and must fail against the current code.)
- A15. With the embedding model unavailable, a chat turn still returns a lexical-only answer and the UI states that semantic retrieval was unavailable.
- A16. Deleting a Source or a Task requires an explicit second confirmation naming the item.
- A17. A Workspace with zero indexed Sources shows a visible warning to Members, not only to the Owner.

**Process**

- A18. `memory.md`, `state.md`, and `changelog.md` exist at the repository root and are current: `state.md` names the correct build-order step and a concrete next action, `changelog.md` has an entry for every completed step, and `memory.md` has a decision-log entry for every `[OPEN]` item encountered.
- A19. No `[OPEN]` item is recorded in `memory.md` as resolved on the agent's own authority. Permitted outcomes are *interim behaviour applied*, *deferred*, or *answered by project owner on `<date>`*.

**Deployment, credentials, and key expiry** (Addendum A, §14)

- A20. With no `.env` file present, the application starts, the Manage view works, and the chat surface shows a clear "no model configured" message rather than a stack trace.
- A21. A `ModelSpec` whose env slug is blank does not appear in the model picker. If `DEFAULT_MODEL_ID`'s slug is blank, the picker opens on the first configured model without raising.
- A22. With `OPENAI_API_KEY_EXPIRES_ON` set 10 days in the future, an Owner sees a persistent orange warning in the sidebar on both the Chat and Manage views, naming the date and the days remaining. Chat, uploads, and every Manage action continue to work unchanged.
- A23. With the same date set 30 days out, no warning is shown. With it set in the past, all users — Owner and Member — see a red expired notice. With it unset or malformed, `api_key_status()` returns `unknown` and does not raise.
- A24. `.env` is git-ignored; `.env.example` is committed and contains every variable; no real key or base URL appears anywhere in the repository's history.
- A25. `call_model()`'s signature is unchanged and `tests/test_chat_error_handling.py` still passes.

**Embedded-image visibility and no-model send block** (§15)

- A26. For each ingested PDF/DOCX, the `sources` row stores an `image_count` (the number of embedded images found during parsing); it is 0 or more and never blocks ingestion.
- A27. In Manage → Knowledge, an Owner sees a per-file note "N images — their content is not indexed" whenever that file's `image_count > 0`.
- A28. With no model configured, the chat `st.chat_input` and the task buttons are DISABLED (not hidden) so no message can be sent; the "No AI model is configured" warning is the single explanation, and no send ever fails with a raw `Unknown model_id None`.

**Parsing and answer-presentation fixes** (§7.10–§7.13)

- A29. Section titles are classified by SHAPE, not `unstructured` element type: a numbered heading (`1.`, `2.1`, `3)`) is a heading whatever its element type; a `Title`/`Header` is a heading only if it is short, does not end with a sentence period, and starts uppercase/digit. Body sentence fragments (e.g. "Financial Crime Oversight Committee.", "channel for Severity 1.") are body text, never section titles.
- A30. The chip row under an assistant message is labelled "Retrieved from" and is presented as the RETRIEVED chunk set — it does not claim to be the model's inline citations.
- A31. Chips are deduped by `(display_name, section_title)`, so two chunks from the same document section render once.
- A32. The model-turn spinner sits INSIDE the assistant message bubble and transitions directly into the answer in the same render; the answer does not appear only after a separate rerun following the spinner's removal.

**Message timestamps and chat export** (§16)

- A33. Every message in the UI shows its timestamp; stored `created_at` remains UTC, and the displayed value is the user's local time. Display-only — no schema change.
- A34. An Owner/user can export the active Chat as a Markdown file containing, per turn, the question, the answer, the retrieved sources, the model (display name + slug), and the timestamp.
- A35. `tests/offline_retrieval_eval.py` takes a second CLI argument (`aml` / `hr` / `sec` / `all`) selecting which of `AML_QUESTIONS` / `HR_QUESTIONS` / `SEC_QUESTIONS` / the combined set runs, without editing the file between runs; the scoring logic, `TOP_K`, and everything in `retrieval/` are unchanged.
- A36. After the first question in a new Chat, the Chat remains selected, its title updates to the question, and the question and answer remain visible without a refresh; switching Chats by hand and "+ New chat" still work.

**Grounding rules in the system prompt** (§18) — verified by the hand-run adversarial set (§18.2), not by an automated test.

- A37. A gap the documents reveal is stated and stopped at: nothing is added after "the documents do not say" — no general knowledge, no "typically", no textbook definition, no plausible inference.
- A38. No date, duration, or elapsed time is calculated or inferred from a value the documents do not contain.
- A39. Document silence is never presented as a rule — "not stated" is not "continuous", "always", "never", or "no exception".
- A40. Two sources are described as agreeing or disagreeing only when BOTH address the subject; when only one does, the answer says so.
- A41. A question with several possible answers gets all of them, labelled, or a request to clarify — never one picked silently.

**Activity logging** (§19) — decided; not built.

- A42. Logs are written to their own SQLite database, separate from the knowledge-base database: the main database gains no log table, the log database holds no knowledge-base, chat, Workspace-configuration, or membership rows, and a burst of logging can never block a chat/API question through SQLite's single-writer lock on the main database. The log database is never part of a knowledge-base backup.
- A43. Knowledge base, chats, Workspace configuration, and membership stay in the one existing database, separated by `workspace_id`; deleting a Workspace remains a single atomic action. (Decided; recorded so it is not revisited on tidiness grounds.)
- A44. Tier 1 logging is always on and records exactly the metadata fields listed in §19.2 — never question or answer text — and contains nothing privacy-sensitive, so it may be retained freely.
- A45. Tier 2 logging is OFF by default; it is enabled per Workspace by that Workspace's Owner, records question text, answer text, and retrieved chunk identifiers only while enabled, and the UI states plainly what is stored while it is on.
- A46. The refusal rate is computable from Tier 1 alone: the per-turn row records `workspace_id`, a timestamp, and an `outcome` distinguishing `answered` from `refused` and `error`, so the rate can be sliced by Workspace and over time. (Determining `refused` depends on a refusal signal — see OPEN-15.)
- A47. Log storage is the SQLite log database alone, with no per-session text files; retention and deletion act on that database independently of the knowledge-base database. (Recommendation recorded per §19.4.)

**Service interface** (§20) — specified; not built.

- A48. The API's division of responsibility is stated: OC_KB_Pro owns Workspace/document isolation, ingestion and indexing, retrieval, grounded answer generation, citation selection, refusal when the documents do not support an answer, Workspace instructions, and knowledge-base access control; the calling system owns the case/task, customer/account/transaction data, workflow state, business logic, question choice, handling of the answer, actions, human approval, and outcome recording.
- A49. The endpoint accepts a request identifying the Workspace (`workspace_id`, not name — names are non-unique, OPEN-5), the question, and an optional model; a malformed or incomplete request is rejected with a documented `400`.
- A50. A successful response returns the answer text and structured sources — document, section, and page where the source format supports it — never a prose citation; the response contains no `grounded` flag (deferred to OPEN-15), and an empty `sources` list is the only interim signal.
- A51. A caller is identified by an API credential mapped to Workspace memberships; an unknown or invalid caller is rejected. The API is a post-PoC surface and MUST NOT be built or exposed until OPEN-13 and OPEN-14 are resolved; constraint C6's no-authentication rule governs the in-app UI only.
- A52. When retrieval finds nothing, the response is the documented refusal with an empty `sources` list, and no content is fabricated.
- A53. Bad Workspace, unknown caller, provider failure, oversized request, no model configured, and malformed request each return a distinct documented HTTP status and machine-readable error code, with no stack traces.
- A54. Rate limiting is specified as required and per-caller, with the reason recorded (a single shared provider credential and the SQLite single writer); the limit value is a deployment parameter, not fixed here.

**Tier 1 logging — built** (§19) — 2026-09-15.

- A55. Tier 1 activity logging (§19.2) is implemented: every question writes one Tier 1 row — from the UI (`source="ui"`) and the API (`source="api"`) alike — recording exactly the listed metadata fields and **no** question or answer text. The log database is a separate SQLite file (`data/logs.db`) opened with WAL + `busy_timeout`; the main database is unchanged and needs no schema change for the two writers.

**Service interface — staging subset built** (§20.9–§20.13) — 2026-09-15; PoC/staging scope, superseded before production.

- A56. The API is a separate process (`service/api.py`) that reuses `retrieval/`, `prompting/`, and `models/` with no duplicated retrieval/prompt/answer logic, and has no API code inside the Streamlit app.
- A57. The API binds to `127.0.0.1` only and refuses to start if configured to bind elsewhere, with an error naming OPEN-13 and OPEN-14. This loopback binding — not policy — makes the staging API network-unreachable despite the unanswered access questions.
- A58. A single static key `KB_API_KEY` (from `.env`) authenticates the caller via a request header; a missing or wrong key returns the documented `401`, produces no answer, and still writes a Tier 1 row. This is explicitly not the production model (shared secret, no per-caller identity, no revocation, no audit).
- A59. The endpoint accepts `{workspace, question, model?}` (`workspace` is the id, never the name) and returns `{answer, sources}` where each source is structured `{document, section, page}` and `page` is `null` where the stored format does not support it. The response contains no `grounded` flag.
- A60. When retrieval finds nothing, the API returns the documented refusal with `sources: []` and does not fabricate content.
- A61. The API returns distinct documented errors — machine-readable codes, no stack traces — for unknown workspace, bad/missing key, no model configured, provider failure, oversized request, and malformed request.
- A62. Rate limiting is deliberately absent in staging (one localhost caller); A54 remains the production requirement. Per-caller identity/membership mapping and Tier 2 logging are likewise not built.
- A63. The empty-retrieval refusal signal is applied identically on the UI and the API: a completed UI turn with zero retrieved chunks logs `outcome='refused'` while still calling the model (no short-circuit added to the UI), matching the API. The signal is documented as under-counting refusals (chunks retrieved but not answering are logged `answered`) until OPEN-15 is answered (SPEC §19.6).

---

## 11. Open questions

Consolidated. Each must be answered by the project owner; none should be resolved by the implementing agent alone.

| # | Question | Interim behaviour | Why it matters |
|---|---|---|---|
| **OPEN-1** | Where is spec v2? Section references throughout the code are unverifiable without it. | Treat the code's docstrings as the authority. | This document may contradict v2 in ways nobody can currently detect. |
| **OPEN-2** | Is the `call_model(prompt, model_id)` widening of constraint C4 approved? Are the `provider_model_name` slugs and the 256k context figures in `models/registry.py` correct? | **Updated, not closed, by Addendum A (§14).** The widening is now confirmed — §14.4 mandates `call_model(prompt, model_id) -> str` stays as the single call site with an unchanged signature, and real slugs / base URL / key are supplied via `.env` (§14.3). What remains open: confirming each model's real `context_window_tokens` against the actual endpoint. | The registry's context-window numbers feed `fits_in_context()`. Wrong numbers mean a wrong guard. **Under §20 this becomes materially more serious:** a calling system pasting case context can exceed the real limit and the provider will reject the request. The real `context_window_tokens` must be confirmed against the live endpoint **before the API is built**. |
| **OPEN-3** | **Does a Chat's prior turns go into the prompt?** (§3.3, §6.5) | Option A — no history in prompt. | Determines whether "multiple Chats" is a context-management feature or a UI organisation feature. Changes the v2 assembly order if Option B. |
| **OPEN-4** | Who is a member of a newly created Workspace? (§5.3) | All `TEST_USERS`, mirroring the existing seed. | Under the interim rule an Owner cannot create a private Workspace. |
| **OPEN-5** | Should Workspace names (and Task names) be unique? | Not enforced. | Duplicate names in a selectbox are indistinguishable to the user. |
| **OPEN-6** | Can a Workspace be renamed or deleted? What happens to users currently in it, and to the last remaining Workspace? (§5.5) | Neither is built. | Without delete, an Owner experimenting with segregation accumulates dead Workspaces and their embeddings. |
| **OPEN-7** | How is a Chat titled? (§6.2) | First 60 characters of the first user message. | A model-generated title costs an extra call; a user-editable title needs UI. |
| **OPEN-8** | Can a Chat be renamed or deleted? | Neither is built. | Same accumulation problem as OPEN-6, at higher volume. |
| **OPEN-9** | Should any of the accepted limitations in §7.9 be addressed for this PoC? | None addressed. | Several (stopword filtering especially) would change retrieval behaviour and invalidate evaluation runs. |
| **OPEN-10** | Is there a cross-Workspace question path — e.g. searching several Workspaces at once? | No. Retrieval is strictly single-Workspace. | This is the main functional cost of segregation (§3.1). |
| **OPEN-11** | Is the endpoint an OpenAI-compatible proxy, Azure OpenAI, or `api.openai.com` directly? (§14.4) | Implement the OpenAI-compatible case. Stop and ask if a real call fails in a way that suggests Azure. | Azure needs a different client class, an `api-version`, and deployment names rather than model slugs. |
| **OPEN-12** | Who sees the pre-expiry warning? (§14.5) | `expiring`/`unknown` to Owners; `expired` to everyone. | Members cannot renew a key, but they are the ones whose chat breaks when it lapses. |
| **OPEN-13** | The internally deployed app has no authentication — anyone reaching the port can sign in as Owner and manage or delete any Workspace. Is the host network-restricted, or does the PoC need a gate before deployment? (§14.1) | None. Flagged only. Do not build authentication. | Constraint C6 was written for laptop testing with three users, not for a deployed internal host. |
| **OPEN-14** | Is the Streamlit port network-restricted to entitled users, or merely reachable on the internal network by anyone who knows the address? | Unverified; treat "anyone who can open the app is already authorised" as an assumption, not a fact. | §17 F10's identity model rests entirely on this premise. If the port is merely reachable, self-declared identity is not an access control at all. Related to OPEN-13 but not the same question — OPEN-13 asks whether a gate is needed, OPEN-14 asks whether one already exists. |
| **OPEN-15** | Should the API response include a `grounded: true/false` flag? (§20.3) | None. Do not add the field. | A calling system branches on it automatically, with no human reading the answer, so a wrong flag is worse than no flag. The application cannot observe whether an answer was grounded: it could only **parse the model's own "(Source: …)" text** — the approach explicitly rejected for the citation chips (§7.11) — or **ask the model to declare its own honesty**. A third option is to return `sources` and let the caller decide from an empty list. Higher-stakes than the chip relabelling was, because no human sees the answer. Undecided. |
| **OPEN-16** | Does retrieval degrade when case context is pasted into the question? (§20.1, §20.2) | Unmeasured. Assume it may. | The intended workflow pre-processes a case externally and sends a question containing the case context inline, but search uses the ENTIRE question text as the query — so account numbers, amounts, and dates become search terms that appear nowhere in the procedures. Retrieval may get worse exactly when the question is richest. Needs measuring (short / medium / long context) before the API design is finalised. |
| **OPEN-17** | Chat retention — keep only the last 10 conversations? | Nothing deleted; no cap. | Chats are plain text and storage is not the constraint, so deleting a user's work to reclaim space that was never short is a poor trade. The real problem is a cluttered selector, which is a **display** concern (show recent, collapse the rest), compounded by the missing delete action (OPEN-6 / OPEN-8). Both positions recorded; undecided. |

---

## 12. Explicitly out of scope

Do not build these. They are not in the draft or the brief, and adding them would exceed the PoC's stated boundaries.

- Authentication, SSO, user invitation, user removal, password handling (constraint C6). **PoC-scope only:** out of scope for this PoC under constraint C6, and superseded post-PoC by §17 F10, which replaces the hardcoded test users with a per-Workspace identity and permission model.
- Live `/` autocomplete in the chat input (constraint C7).
- Confluence ingestion or any `source_type` beyond `pdf`/`docx`/`xlsx`.
- A vector database, ANN index, or FAISS. Brute-force cosine is the specified approach at this scale.
- Reranking models, query expansion, or HyDE.
- Cross-Workspace search or source sharing between Workspaces (OPEN-10, OPEN-6).
- Sharing a Chat between users, or any collaborative-editing behaviour.
- Response streaming, per-message feedback capture, analytics, or usage metering.
- Changing `top_k`, `MAX_RETRIEVED_TOKENS`, `rrf_k`, `candidate_pool`, or chunk-size targets without evaluation evidence (constraint 8, §9.3).
- Splitting oversized chunks in `ingestion/chunking.py` (§7.2).

---

## 13. Project journal — required files

Three files at the repository root, created in the first commit and updated throughout. They are working instruments, not documentation: the agent's context window will not survive this project, and these files are what carries decisions across that boundary.

### 13.1 The boundary rule

| File | Answers | Write pattern |
|---|---|---|
| `memory.md` | **Why** — decisions, discoveries, things learned the hard way | Append-only. Never edit or delete a past entry. |
| `state.md` | **Where** — current position, right now | Overwritten every update. Keep it under one page. |
| `changelog.md` | **What** — changes actually shipped | Append-only, newest first. |

A fact goes in exactly one file. A decision goes in `memory.md`; a position goes in `state.md`; a code change goes in `changelog.md`. Cross-reference by build-order step number or `[OPEN]` id instead of duplicating text. Duplication is how these files rot.

### 13.2 `memory.md`

Four required sections.

**Decision log.** One entry for every `[OPEN]` item encountered (§11), plus any judgement call not covered by the spec. Format:

```
### OPEN-4 — Workspace membership — 2026-xx-xx
Question: Who is a member of a newly created Workspace?
Outcome: Interim behaviour applied (SPEC §5.3 — all TEST_USERS added).
Authority: Agent applied spec interim. NOT answered by project owner.
Consequence: An Owner cannot create a private Workspace. Still needs a decision.
```

**The `Authority` line is mandatory and has exactly three permitted values:** *Agent applied spec interim*, *Deferred — not reached*, or *Answered by project owner on `<date>`*. The agent never writes the third one about itself (§10, A19).

**Codebase discoveries.** Non-obvious facts learned by reading or running the code — the kind of thing that costs an hour to rediscover. Examples of the register: external-content FTS5 rows must be deleted before their content rows; `test_build_prompt_respects_token_budget` still passes under `continue` because both its chunks are 2600 tokens.

**Rejected approaches.** What was tried, why it was abandoned. This is what stops a later session re-litigating a settled question.

**Deviations from the spec.** Anything built differently from `SPEC.md`, with the reason. If the spec is wrong or unimplementable, that belongs here *and* in the final report — do not quietly diverge.

Entries are dated, three to six lines, and factual. If a past entry turns out to be wrong, add a new entry saying so and naming the one it supersedes. Do not rewrite history.

### 13.3 `state.md`

Overwritten in place. Five sections, nothing else:

- **Current step** — which build-order step (§9) and its status.
- **Progress** — Done / In progress / Not started, by step number.
- **Blocked on** — unanswered `[OPEN]` items that are *actually* blocking, and what is needed to unblock. Empty is a valid and good answer.
- **Test status** — the verbatim result of the last `python -m pytest tests/ -q` run, with counts and the date.
- **Next action** — exactly one concrete instruction, specific enough that a fresh session can act on it without rereading the whole spec. "Continue work" fails this test. "Fix `break` → `continue` at `prompting/assemble.py` line ~56, then run the test suite" passes.

The test: if this session ended right now and a new one opened tomorrow with no memory, could it start work from `state.md` alone? If not, it is not finished.

### 13.4 `changelog.md`

Append-only, newest entry at the top. One entry per completed build-order step, or per commit if a step spans several. Each entry:

- Date, step number, one-line summary.
- Files added / modified / deleted.
- Acceptance criteria now satisfied, by A-number (§10).
- **Schema and migration changes called out explicitly**, under their own heading. Step 3 touches the database; a reader six months from now needs to find that without reading diffs.
- Anything left known-broken or deferred, and why.

### 13.5 When to write

- **Before starting a step** — refresh `state.md`.
- **On hitting an `[OPEN]` item** — write the `memory.md` decision-log entry *immediately*, before continuing. Not at the end of the session. This is the entry most likely to be lost, and the most expensive to lose.
- **On learning something non-obvious about the code** — `memory.md`, while it is still fresh.
- **On finishing a step** — `changelog.md` entry, `state.md` refresh, run the tests and record the result.
- **Before ending a session** — `state.md` must stand on its own.

### 13.6 What not to do

- Do not narrate routine work into `memory.md` ("read `app.py`", "ran the tests"). It records decisions and discoveries, not activity.
- Do not copy spec content into any of the three files. Reference `SPEC.md §x.y` instead.
- Do not let `state.md` accumulate history — that is what `changelog.md` is for. If `state.md` is growing, something is in the wrong file.
- Do not put project status in `README.md` or `SPEC.md`. Those describe the system; the journal describes the work.
- Do not treat the journal as a deliverable to write up at the end. Written afterwards from memory, it is worth roughly nothing.

---

## 14. Deployment, credentials, and API key expiry

From Addendum A (`SPEC-addendum-A-provider-and-key-expiry.md`), merged per its top-of-file
instruction. Tag conventions as per §0.1.

### 14.1 Deployment context `[NEW]`

The application is deployed and used **internally within the company**. It is not publicly accessible.

**What this confirms:** constraint C6 (no authentication, hardcoded `TEST_USERS`) remains acceptable for this PoC. It is not an oversight to be corrected.

**What this does not change:** secrets are still never committed to the repository, never written to the database, and never logged. An internal network is a smaller attack surface, not an absent one.

**What it raises `[OPEN-13]`:** the application has no authentication of any kind. Anyone who can reach the Streamlit port can select "Alex (Owner)" from the sign-in selectbox and thereby upload to, edit, or delete any Workspace, including its knowledge sources. On a laptop with three test users this is harmless. On an internally deployed host it means Workspace management is available to every person on the network who knows the URL. This is a deployment decision for the project owner — whether the host is access-restricted at the network layer, or whether the PoC needs some gate before it is deployed. **Do not build authentication in response to this.** Flag it and continue.

### 14.2 Configuration via `.env` `[NEW]`

Deployment-specific values move out of code and into environment configuration.

**Files:**

- **`.env.example`** — committed to the repository. Contains every variable with an empty or clearly placeholder value and a short comment. This is the file the addendum's "placeholders" requirement refers to.
- **`.env`** — **never committed.** Add it to `.gitignore` alongside the existing `data/` and `.venv/` entries. The developer copies `.env.example` to `.env` and fills in real values at configuration time.

Committing a real `.env` with placeholder values is not acceptable even though the values are fake: the file then exists in git, someone fills it in locally, and the first `git add -A` commits live credentials. The example-file pattern makes that mistake require deliberate effort.

**Variables:**

```dotenv
# Base URL of the OpenAI-compatible endpoint.
OPENAI_BASE_URL=

# API key for the endpoint above.
OPENAI_API_KEY=

# Date the API key expires, as YYYY-MM-DD (e.g. 2026-12-31).
# Entered manually by whoever configures the deployment; there is no way to
# read this from the provider. Leave blank if unknown — the app will run
# normally and simply will not be able to warn before expiry.
OPENAI_API_KEY_EXPIRES_ON=

# Model slugs exactly as the endpoint expects them, one per selectable model.
# Leave a slug blank to hide that model from the picker.
OPENAI_MODEL_FAST=
OPENAI_MODEL_STANDARD=
OPENAI_MODEL_REASONING=
```

**Loading — there is a trap here.** `models/router.py` currently reads its key at module import:

```python
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")
```

That line is evaluated when the module is first imported, which happens via `ui/chat_view.py` during `app.py`'s import block — potentially before any `load_dotenv()` call runs. **Remove it.** Every environment read must happen **lazily, inside the function that needs the value**, never at module scope. In addition, call `load_dotenv()` once at the top of `config.py` (which `app.py` imports early) so the values are present regardless.

Add `python-dotenv` to `requirements.txt`.

The application must start and run normally with no `.env` file present. Absent configuration degrades to a clear, non-crashing message (§14.3, §14.5) — never a stack trace on startup.

### 14.3 How `.env` and `models/registry.py` divide responsibility `[NEW]`

`SPEC.md` §8 rule 7 says model metadata lives in `models/registry.py`. This addendum splits that, and the split is the rule:

| Lives in `.env` | Lives in `models/registry.py` |
|---|---|
| Base URL | `model_id` (stable key used in DB rows and session state) |
| API key | `display_name` shown in the picker |
| API key expiry date | `notes` shown beside the picker |
| `provider_model_name` (the slug the endpoint expects) | `context_window_tokens` |

The distinction: **`.env` holds what changes between deployments; the registry holds what the user sees.** A second environment pointing at a different endpoint should need no code change.

**Resolution rules:**

- A `ModelSpec` whose env slug is empty or unset is **omitted from the picker entirely.** Do not show a model that cannot be called.
- **The picker MAY surface each model's `.env` slug as read-only secondary context** (e.g. "Standard (openai/gpt-4o)"), so the user can see which real model answers. This does not break the split: the registry's `display_name` remains the source of the human label, `.env` remains the source of the slug, and the picker only *displays* the env value by reading it via `provider_model_name()`.
- If `DEFAULT_MODEL_ID`'s slug is not configured, fall back to the first configured model. `_render_model_picker()` currently does `[m.model_id for m in models].index(DEFAULT_MODEL_ID)`, which raises `ValueError` if the default is absent — that path must not crash.
- If **no** model is configured, the picker renders nothing and the chat surface shows a clear message that no model is configured, naming `.env` as the place to fix it. The app stays up; Manage and ingestion continue to work.
- The `context_window_tokens` value of 256,000 in the registry is **still an assumption** carried from the original note. Once real slugs are known, confirm the real window for each and correct the registry — `fits_in_context()` guards against overflow using that number, so a wrong figure means a wrong guard. This updates, and does not close, `[OPEN-2]`.

### 14.4 Router adapter `[NEW]`

Constraint C4 is unchanged: `call_model(prompt, model_id) -> str` remains the only function that talks to a provider, and **its signature does not change.** `tests/test_chat_error_handling.py` monkeypatches `ui.chat_view.call_model`; that must continue to work.

- Replace the `internal_gateway` provider and `_call_internal_gateway()` placeholder with an OpenAI-compatible adapter. The dispatch structure in `call_model()` stays as it is — one branch per provider.
- Construct the client **inside** the adapter function, not at module scope (§14.2).
- **Do not add error handling here.** Let provider exceptions propagate. `_answer()`/`_run_turn()` already catch them and render the inline error with retry (§7.1, shipped in Step 1). A second layer would swallow the detail the expander is meant to show.
- Do not log the prompt or the API key.

**`[OPEN-11]` — which client?** "OpenAI base URL" is ambiguous between three cases that need different code:

1. **An OpenAI-compatible internal proxy or gateway** — `openai` SDK, `OpenAI(base_url=..., api_key=...)`, model slug passed as `model`. This is the assumption the rest of this section is written against.
2. **Azure OpenAI** — same SDK but `AzureOpenAI`, requiring an `api-version` and using *deployment names* rather than model names.
3. **`api.openai.com` directly** — case 1 with the default base URL.

Confirm which before adding an SDK to `requirements.txt`. If the answer is Azure, `.env` needs an additional `OPENAI_API_VERSION` variable and `OPENAI_BASE_URL` becomes the Azure endpoint. **Do not guess** — implement case 1, and if the first real call fails in a way that indicates Azure, stop and ask rather than adapting on the fly.

### 14.5 API key expiry warning `[NEW]`

**Requirement:** starting 14 days before the configured expiry date, the application displays a persistent, clearly visible warning that the API key is approaching expiry and needs renewal. The warning is informational only. It must never block or degrade any functionality.

**Status function.** Add `models/credentials.py` with a single public function:

```python
api_key_status() -> KeyStatus
```

returning a frozen dataclass with `state`, `expires_on`, and `days_remaining`, where `state` is one of `"ok"`, `"expiring"`, `"expired"`, `"unknown"`.

- No Streamlit import (`SPEC.md` §8 rule 2). This module computes; `app.py` renders.
- `KEY_EXPIRY_WARNING_DAYS = 14` is defined here, as a named constant with a comment, not inline in the UI.
- Date format is `YYYY-MM-DD`, compared against **today's UTC date** (the application uses UTC ISO timestamps throughout — see `_now()` in `config.py`, `db.py` callers, and both view modules).
- The key is treated as valid **through the end of the named day**. `days_remaining = (expires_on - today_utc).days`; `0` means it expires today and is still usable.
- `state` resolution: `expired` when `days_remaining < 0`; `expiring` when `0 <= days_remaining <= 14`; `ok` above that; `unknown` when the variable is unset, empty, or unparseable.
- **`api_key_status()` never raises.** A malformed date returns `unknown`. This function is called on every render; an exception here would take down every page.

**Rendering.** In `app.py`'s sidebar, so it is present on every screen in both the Chat and Manage views, and survives Workspace and Chat switching. Use the existing pill components (`ui/pills.py`) and the existing five-family colour system — do not introduce a new visual treatment:

| State | Shown | Treatment |
|---|---|---|
| `expiring` | The expiry date and days remaining, with a short line saying the key needs renewing | `orange` |
| `expired` | That the key expired on the named date and answers will fail until it is renewed | `red` |
| `unknown` | That no expiry date is configured, so no advance warning is possible | `gray` |
| `ok` | Nothing | — |

**Non-interference — these are requirements, not guidance:**

- The warning never disables the model picker, the chat input, the task buttons, uploads, or any Manage action.
- It is never a modal, never an overlay, never `st.stop()`.
- It is not re-checked inside `call_model()` or on any model call. It is a display concern evaluated once per render.
- Expiry itself blocks nothing. When the key has actually expired, calls fail at the provider and §7.1's existing inline error with retry handles it. Do not add a pre-flight check that refuses to call.

**`[OPEN-12]` — who sees the pre-expiry warning?** The brief says "the relevant users" without defining them. A Member cannot renew a key; showing them a countdown for 14 days is noise. But once the key expires, every Member's chat breaks and they need to know why.

**Interim behaviour (implement this):** `expiring` and `unknown` are shown to Owners only. `expired` is shown to **all** users. Flag the question; do not treat the interim as settled.

### 14.6 Explicitly out of scope for this addendum

- Auto-renewal, or any call to the provider to verify key validity. The expiry date is manually entered and manually maintained; that is the whole mechanism.
- Storing the API key or the expiry date in the database.
- Displaying the key, or any prefix or suffix of it, anywhere in the UI.
- Email, Slack, or any out-of-app notification.
- A second configuration mechanism. `.env` is it — no YAML, no JSON, no `secrets.toml`, no settings UI.
- Per-Workspace or per-user model credentials. One endpoint, one key, application-wide.
- Building authentication in response to §14.1.

---

## 15. Embedded-image visibility and no-model send block

New work beyond Addendum A, added 2026-09-11 at the project owner's request. Tag
conventions as per §0.1.

### 15.1 Embedded-image visibility at upload `[NEW]`

The real back-office procedures are image-heavy (screenshots, diagrams, scanned
figures). The pipeline (SPEC §2/§7) extracts and indexes **text only** — image
content is never read. To make that gap visible to the Owner rather than silent
(the mixed text-plus-screenshots case fails silently; only a fully-scanned PDF
fails loudly via the zero-sections `failed` path), count embedded images per file
during parsing.

**Count, stored on the `sources` row:**

- Add a nullable `image_count INTEGER` column to `sources` via the existing
  `migrate_db()` pattern (SPEC §4.5). NULL/absent means "not counted" (e.g. rows
  inserted before this column or an XLSX, which has no meaningful embedded-image
  count for this purpose).
- During `parse_pdf` / `parse_docx`, count the embedded images:
  - **PDF:** `Image`/`Figure`-type elements from the `unstructured` stream, or a
    pypdf XObject scan in the fallback path.
  - **DOCX:** `python-docx` `document.inline_shapes` (and drawings via XML), or
    `Image`-type `unstructured` elements.
- Only what is already installed — **no new dependency.**
- The count never blocks ingestion; it is written alongside `status='indexed'`.

**UI (Manage → Knowledge, Owner only):**

- For a Source with `image_count > 0`, show a note under that file:
  "N images — their content is not indexed", using the existing caption/pill
  style. No new visual language.

**Known limitation — the count is a floor:** vector diagrams and curve-rendered
text may not register as countable raster images, so the count is a lower bound,
never a guarantee about how much image content exists. It flags presence, not
semantic content.

**Explicitly out of scope:** OCR and image reading of any kind. The image content
is not extracted, transcribed, or embedded — the warning only surfaces its
presence. (See memory.md — OCR scoped-and-deferred.)

### 15.2 No-model send block `[NEW]` — amends §14.3/A20

When no model is configured (`list_models()` empty), the app already shows
"No AI model is configured" (SPEC §14.3, A20). A gap: the send paths stayed
enabled, so a message could still be typed and would fail with a raw
`Unknown model_id None` in the §7.1 bubble — not the clear single message A20
intended.

**Behaviour:** with no model configured, the chat `st.chat_input` and the task
buttons are DISABLED (not hidden), so no send can occur. The existing warning is
the single explanation — it reads as "fix your config", not "the app is broken".
Disabling (rather than hiding) keeps the layout stable and signals the controls
exist but are gated on configuration.

---

## 16. Message timestamps and chat export

New features, added 2026-09-11 at the project owner's request. Tag conventions
as per §0.1.

### 16.1 Per-message timestamps `[NEW]`

Every message shown in the chat view displays its timestamp. `chat_messages`
already stores `created_at` as a UTC ISO string (SPEC §4.3); this is
**display-only**: no schema change, and the stored value stays UTC. The UI
converts to the user's **local time** for display only.

- Touches `ui/chat_view.py::render_chat_view` (history loop and the inline
  render) + a small formatter (e.g. in `ui/cards.py`).
- The conversion happens in the UI layer only; `db.py`/`ingestion/` never
  localise timestamps.

### 16.2 Chat export as Markdown `[NEW]`

The user can export the active Chat as a **Markdown** file. For each turn the
export contains: the question, the answer, the retrieved sources ("Retrieved
from"), the model (display name + `.env` slug), and the timestamp.

- Touches a new `ui/export.py` (builds the Markdown from the Chat's messages)
  and `ui/chat_view.py` (a `st.download_button` for the active Chat). No schema
  change; reads `chat_messages` for the active `chat_id`.
- **Privacy — conscious decision (recorded in `memory.md`):** an export takes
  internal procedure content out of the app as an **uncontrolled file**.
  Acceptable for this PoC, run by the owner on their own machine. **Must be
  revisited before the tool is used by other people** (and before any
  deployment — see OPEN-13).

---

## 17. Post-PoC direction (titles only)

The detail for the items below lives in the project owner's vision document,
which is deliberately **not** in this repository. This section exists only so
that earlier sections can reference these items by identifier. It carries no
implementation detail and no acceptance criteria.

- **F1** Default Instructions fallback
- **F2** Retrieval performance fix (fetch only what scoring needs)
- **F3** "This Workspace is getting large" indicator
- **F4** Processing and activity logging
- **F5** Chat export and visible timestamps — **NOTE: built, see §16.2**
- **F6** Specialised Agents within a Workspace
- **F7** Service interface (API / MCP)
- **F8** Reading embedded images (deferred by direction)
- **F9** One database per Owner (evaluate, do not assume)
- **F10** Identity, roles and permissions
- **F11** In-app user guide

None of the remaining items is in PoC scope, and none is built before it is
written into this spec with acceptance criteria.

---

## 18. Grounding rules in the system prompt (prompting/instructions)

The prompt is built centrally in `prompting/assemble.py::build_prompt()` (SPEC
§2 constraint 6, §8 rule 4); the system policy is the `SYSTEM_POLICY` constant
there. Owner-directed rules, added 2026-09-13 after the adversarial run.

### 18.1 The rules `[NEW]`

The system prompt must instruct the model to:

1. **State a gap and stop at it.** When the available knowledge does not answer
   the question, say so and add nothing further about it — no general knowledge,
   no "typically", no textbook definition, no plausible inference. A detected
   gap is an answer.
2. **Never calculate from absent data.** No date, duration, or elapsed time may
   be derived from a value the documents do not contain.
3. **Never read silence as a rule.** If the documents do not state something, it
   is not "continuous", "always", "never", or "no exception" — it is simply not
   stated.
4. **Attribute agreement only when both sources speak.** Two sources may be
   called agreeing or disagreeing only when BOTH address the subject; when only
   one does, say so.
5. **Answer multi-answer questions fully.** A question with several possible
   answers gets all of them, labelled, or a request to clarify — never one
   picked silently.

Plus the existing requirement: answer only from the available knowledge, cite the
source for every claim, and never use outside/general knowledge.

### 18.2 Verification `[NEW]`

These are **not** automatically tested (no test may call the live model). They are
verified by the hand-run adversarial set — the seven confirmed failures of
2026-09-13, recorded as a named regression set in `GROUNDING_REGRESSION.md` at the
repository root. Acceptance criteria: A37–A41.
The fix is **prompt-level only**: `retrieval/`, `top_k`,
`MAX_RETRIEVED_TOKENS`, `rrf_k`, `candidate_pool`, and chunk sizes are NOT
touched.

---

## 19. Activity logging (F4)

Specified 2026-09-14 at the project owner's direction. **Spec-only — nothing here
is built.** There is currently no logging of any kind. Tag conventions as per §0.1.

### 19.1 Storage: logs in a separate database; everything else stays in one

**Logs live in their own SQLite database file, separate from the knowledge-base
database.** The reason is technical, not tidiness:

- SQLite permits **one writer at a time**. Log writes are frequent, small and
  constant, while knowledge-base writes are occasional. Sharing a file would let a
  burst of logging block a user's question — and the problem worsens once an API
  (§20) is calling the service.
- Logs are **disposable** and grow far faster than anything else; they need their
  own retention and deletion.
- Tier 2 logs (§19.2) may hold **question and answer text**, so they must be
  deletable independently and must **never** be part of a backup of the knowledge
  base.

**Everything else stays in the one existing database** — knowledge base, chats,
Workspace configuration, and membership — separated by `workspace_id` exactly as
today. They share a lifecycle, are read and written together, and deleting a
Workspace must remain a single atomic action. Splitting them would add a failure
mode (partial deletes, orphaned rows) to solve a problem that does not exist at
this scale. **Recorded as decided so it is not revisited on aesthetic grounds.**

**Consequences:**

- The main database gains **no** `logs` table; the log database holds **no**
  knowledge-base, chat, Workspace-configuration, or membership rows.
- SQLite foreign keys do not cross database files, so `workspace_id`, `chat_id`,
  and the caller identifier are recorded in logs as **plain values, not foreign
  keys**. No cascade, no referential integrity, by design.
- The log database is opened and written independently of `db.get_connection()`;
  a logging failure must never fail a question.
- The knowledge-base backup is scoped to the main database and the uploaded
  sources; the log database is excluded from it.

### 19.2 Two tiers `[NEW]`

**Tier 1 — ALWAYS ON, metadata only, no question or answer text:**

| Field | Recorded value |
|---|---|
| `timestamp` | UTC instant the turn completed (same clock as §16.1) |
| `workspace_id` | plain value (no cross-database FK) |
| `requester` | `user_id` for UI calls; caller identifier for API calls |
| `source` | `"ui"` or `"api"` |
| `chat_id` | where applicable (UI); absent for API calls |
| `question_chars` | length of the question in characters — never the text |
| `chunks_retrieved` | number of chunks retrieved |
| `lexical_degrade` | whether the §7.3 lexical-only path was used |
| `model_slug` | the provider slug actually used |
| `retrieval_ms` | retrieval time |
| `total_ms` | total response time |
| `outcome` | `answered` / `refused` / `error` |
| `error_type` | where `outcome = error` |

Tier 1 must contain **nothing privacy-sensitive**, so it can be retained freely.
An `outcome` of `refused` (§19.3) is a completed turn, **not** an error.

**Tier 2 — OFF BY DEFAULT, per-Workspace, question and answer text:**

- Records the full question text, the full answer text, and the retrieved chunk
  identifiers.
- Enabled **per Workspace by that Workspace's Owner**, in Manage.
- While it is on, the UI must state **plainly** what is being stored.
- Intended for diagnosing one specific bad answer, then switched off again.
- Tier 1 and Tier 2 are independent: turning Tier 2 off leaves Tier 1 recording.

**Who may switch it:** the **Owner** of the Workspace. A non-owner cannot enable
or disable it.

**Who is told (proposed — owner to confirm, not marked OPEN):** every user of
that Workspace should see a persistent caption while Tier 2 is on, because their
question text is being stored. The proposal is that notification is mandatory;
the owner may override.

### 19.3 The primary metric: refusal rate `[NEW]`

The proportion of questions answered with the refusal — "the documents do not
cover this". **A rising refusal rate means either a gap in the documents or a
regression in retrieval.** Tier 1 must therefore capture enough to compute it:
`outcome`, `workspace_id`, and `timestamp` are the minimum, so the rate can be
sliced per Workspace and over time.

**Observability caveat (ties to OPEN-15).** The application cannot itself observe
whether an answer is grounded or a refusal: it would have to parse the model's own
"(Source: …)" text (rejected for the citation chips, §7.11) or ask the model to
declare its own honesty. Tier 1 therefore **records** the `refused` value, but the
mechanism that reliably produces it is the same unanswered question as OPEN-15 and
is **not decided here**. Until it is, `refused` may be unavailable, and the rate
computed from whichever signal the owner chooses.

### 19.4 Rotation and retention — recommendation `[NEW]`

The owner's earlier idea was one file per session, `log_KB_yyyymmdd_hhmmss.log`.
**Recommendation: use the SQLite log database alone. Do not also write
per-session text files.**

Reasons:

1. SQLite already provides durability, ordering, indexed queries, and cheap
   deletion/pruning by time or Workspace. A second plaintext copy duplicates every
   field — including Tier 2 question/answer text — doubling the deletion surface
   and letting the two copies drift.
2. The one-writer concern that justified a separate database is solved by the
   database. Per-session files reintroduce concurrent writers (several sessions
   writing files at once) and give up the single-writer serialisation entirely.
3. Per-session files fragment the data: computing the refusal rate would mean
   scanning many files, where a database query is one statement.
4. Rotation in SQLite is **time-partitioning and pruning**, not per-session files:
   prune rows older than the retention window, or roll to a dated database file
   (e.g. monthly). That is a retention decision, not a file-naming one.

If a human needs a live tail for hands-on troubleshooting, a **single** rolling
plaintext file is acceptable only as a **derived, non-authoritative convenience**;
it must never hold Tier 2 text, and the database remains the system of record. The
recommendation is that it is not needed.

**Retention (proposed, not decided):** Tier 1 retained freely (it is
non-sensitive); Tier 2 deleted under its own policy and always deletable per
Workspace. The exact window is not fixed here.

### 19.5 Explicitly out of scope for this section

- The monitoring dashboard — deliberately deferred, see §21.
- Log streaming, external log sinks, or shipping logs off the host.
- Tier 2 logging enabled by default, or enabled by anyone other than the
  Workspace Owner.
- Recording the question or answer text in Tier 1 under any circumstances.

### 19.6 Tier 1 build notes (2026-09-15) `[NEW]`

Building **Tier 1 only** (§19.2); Tier 2 stays unbuilt. Decisions taken at build
time:

- **Log database path:** `data/logs.db` — a separate file, git-ignored, excluded
  from any knowledge-base backup (§19.1).
- **Schema:** one table `tier1_turn_log` carrying exactly the §19.2 fields.
  `outcome` permits `answered` / `refused` / `error`.
- **Concurrency:** every log connection sets `PRAGMA journal_mode = WAL` and
  `PRAGMA busy_timeout = 8000`, the same policy as `db.get_connection()` (§6.1).
  WAL allows one writer and many readers; `busy_timeout` absorbs the momentary
  lock between the Streamlit and API processes. Each log write is a single-row
  insert on a short-lived connection.
- **The main database needs NO change.** It already uses WAL + `busy_timeout`.
  The API only **reads** the main database (Workspace instructions + chunks); it
  does not create Chats or Messages (§20.8). So the API adds no writer to the
  main database — no schema change, nothing for the owner to approve.
- **A logging failure never fails a question:** `log_turn()` swallows its own
  exceptions. A question with no log row is acceptable; a failed question because
  logging failed is not.
- **The empty-retrieval refusal signal is applied IDENTICALLY on both surfaces
  (fixed 2026-09-15).** The application cannot observe groundedness (§19.3). On a
  completed turn `outcome` is `refused` **iff `chunks_retrieved = 0`**, otherwise
  `answered`; on a failure it is `error` — **the same rule in the UI and the API**,
  so the two are comparable. The API additionally short-circuits to the documented
  refusal on zero chunks (§20.5); **the UI does not** and still calls the model
  exactly as before. The *log value* is identical; the *behaviour* is unchanged.
- **This signal UNDER-COUNTS refusals.** A turn where chunks came back but the
  documents did not answer is logged `answered`, not `refused`. The wider signal
  is exactly OPEN-15 and is **not decided here**. **Authority: answered by project
  owner on 2026-09-15 (the scope of the interim signal only; OPEN-15 itself
  remains open).** This interim scope stands until OPEN-15 is answered by the
  owner.

**Acceptance criteria:** A42–A47, A63 (§10).

---

## 20. Service interface (API) (F7)

Specified 2026-09-14 at the project owner's direction. **Spec-only — not built.**
This is where the tool's real value is: another application asks this service a
question and uses the grounded answer. Tag conventions as per §0.1.

### 20.1 Division of responsibility `[NEW]`

**OC_KB_Pro owns:** Workspace and document isolation; ingestion and indexing;
retrieval; grounded answer generation; citation selection; refusal when the
documents do not support an answer; Workspace-specific instructions; access control
around the knowledge base.

**The calling system owns:** the case or task itself; customer / account /
transaction data; workflow state and business logic; deciding which question to
ask; deciding what to do with the answer; executing actions; human approval;
recording the outcome.

The service answers questions about documents. It does not know the case, does not
act, and does not decide what the caller should do. Case context reaches it only if
the caller puts it in the question — which is exactly the risk recorded as OPEN-16.

### 20.2 Endpoint and request `[NEW]`

A single endpoint, `POST /v1/answer`, `Content-Type: application/json`.

```
{
  "workspace": "<workspace_id>",
  "question":  "<question text>",
  "model":     "<model_id>"          // optional; the configured default when absent
}
```

- `workspace` is the **`workspace_id`**, not the name — names are non-unique
  (OPEN-5) and must not be an addressing key over the API.
- `model` is optional; when absent the configured default model is used, exactly
  as the UI's picker default is (§14.3).
- No conversation history is sent: §6.5 / OPEN-3 Option A stands — every turn is
  answered independently.

### 20.3 Response `[NEW]`

```
{
  "answer":  "<answer text>",
  "sources": [
    { "document": "Incident_Response_Procedure.docx",
      "section":  "3. Escalation Timeline",
      "page":     4 }
  ]
}
```

- `sources` is **structured data, not a prose citation**: the document, the
  section, and the page **where the source format supports it** (PDF). `section`
  and `page` may be `null` (e.g. XLSX, or a document with no detected heading).
- `sources` is the **retrieved set** — the same set the UI shows as "Retrieved
  from" (§7.11) — not text parsed out of the model's answer. Parsing the model's
  prose citations was rejected for the chips and stays rejected here.
- **No `grounded` flag.** Whether the response should carry a `grounded:
  true/false` is OPEN-15; until it is answered, the only groundedness signal is an
  empty `sources` list. Do not add the field (A50).

### 20.4 Caller identity and authorisation `[NEW]`

- A caller is identified by an **API credential** presented with the request, not
  by a self-declared user id. The credential maps to an identity and to a set of
  Workspace memberships; a caller may query only a Workspace it is a member of.
- Unknown or invalid credential → `401`. A Workspace outside the caller's
  membership → `404` (not `403`), so the service does not disclose which
  Workspaces exist.
- **Relationship to C6 / OPEN-13 / OPEN-14:** constraint C6 ("no authentication")
  governs the **in-app UI**, a laptop PoC with three hardcoded users. The API is a
  different surface, called by other systems with no human in the loop. It MUST
  NOT be built or exposed until OPEN-13 (is a gate needed?) and OPEN-14 (does one
  already exist?) are resolved. This section specifies the design; it does not
  authorise the build.
- The credential is stored outside the repository and outside the database, as
  `.env` values are (§14.2). It is never logged: Tier 1 records the caller
  identifier, not the credential.

**Amendment (2026-09-15) — staging exception.** §20.9–§20.13 define a
**localhost-only** staging build, permitted *despite* the constraint above because
it is unreachable from the network **by construction, not by policy**. It does not
answer OPEN-13 or OPEN-14 and does not depend on their answers; production remains
blocked until they are resolved.

### 20.5 When retrieval finds nothing `[NEW]`

If retrieval returns no chunks, the response is the documented refusal
("the documents do not cover this") with `sources: []`, and **no content is
fabricated**. A short-circuit that skips the model call is a permissible
implementation and must not change the observable response; whether the model is
called at all is an implementation choice, not a contract.

### 20.6 Errors `[NEW]`

Every error returns `Content-Type: application/json`:

```
{ "error": { "code": "<machine_code>", "message": "<human text>" } }
```

and **never** a stack trace — the same no-crash principle as §7.1.

| Condition | HTTP | `code` |
|---|---|---|
| malformed JSON, or missing `question`/`workspace` | 400 | `invalid_request` |
| unknown or inaccessible `workspace` | 404 | `workspace_not_found` |
| unknown or invalid caller | 401 | `unauthenticated` |
| no model configured | 503 | `model_unavailable` |
| provider failure or timeout | 502 | `provider_error` |
| request or question exceeds the accepted size | 413 | `request_too_large` |
| rate limit exceeded | 429 | `rate_limited` |

Retrieval degrading to lexical-only (§7.3) is **not** an error: the request
succeeds and the answer is produced from lexical results. The degrade is recorded
in Tier 1 (`lexical_degrade`), not surfaced as a failure.

### 20.7 Rate limiting `[NEW]`

**Needed, per caller.** Reasons:

- One **shared provider credential** backs every model call. A single runaway
  caller can exhaust the key and deny the service to everyone else — no human is
  pacing an API.
- SQLite permits **one writer at a time** on both databases; an unpaced caller can
  keep the writers busy.
- Accidental loops (a caller retrying on any non-200) are the common case; a limit
  turns them into a visible `429` rather than a silent outage.

A simple fixed-window per-caller limit (requests per minute) is sufficient at this
scale. The **value is a deployment parameter**, not fixed here. The limit may live
in the service or at the network layer in front of it; either is acceptable, and
this does not prescribe which.

### 20.8 Explicitly out of scope for this section

- Streaming responses (already out of scope, §12).
- Batch or asynchronous endpoints, webhooks, or callbacks.
- Cross-Workspace queries (OPEN-10).
- Persisting API calls as Chats, or any chat lifecycle for API calls.
- Conversation history in the request (§6.5 / OPEN-3 Option A).
- The `grounded` flag (OPEN-15).
- Choosing an API-key-management product or an authentication scheme — that is
  OPEN-13/OPEN-14 and, post-PoC, §17 F10.
- MCP transport specifics: F7 names "API / MCP"; this section specifies the answer
  contract, which either transport would carry. Do not build either yet.

### 20.9 Staging subset — scope and architecture `[NEW]`

Specified and built 2026-09-15 for a staging environment the owner controls, to
exercise the service end to end before the production questions (OPEN-13,
OPEN-14, OPEN-15) are settled. **Everything in §20.9–§20.13 is PoC/staging scope
and is superseded before production.**

- The API is a **separate process** (`service/api.py`, started with
  `python -m service.api`) that **reuses** `retrieval/hybrid_search.py`,
  `prompting/assemble.py`, and `models/router.py`. It duplicates none of that
  logic, and it contains **no API code inside the Streamlit app**.
- API calls are **not** persisted as Chats or Messages (§20.8).
- The API reads the existing main database for Workspace instructions and chunks;
  it writes only to the log database (§19).
- **Named staging deviation from OPEN-2:** the staging API is built on the
  **unconfirmed 256,000-token context-window assumption**. The 256 KiB
  request-body cap (§20.12) is a flat size guard, **unrelated** to the model's
  real context limit — a request under 256 KiB can still exceed the provider's
  real limit and surface as a `502 provider_error`. This is **most likely to bite
  during the OPEN-16 measurement** (§11), where long case context is the point.
  OPEN-2 is **not answered here**; the real windows must be confirmed against the
  live endpoint before production.

### 20.10 Binding — the OPEN-14 containment `[NEW]`

**Loopback binding is the entire access control for staging, and it is not
negotiable.**

- The service binds to **`127.0.0.1` only** — never `0.0.0.0`, never a LAN or
  host address.
- If configured to bind anywhere else, the service **refuses to start**, with an
  error that names **OPEN-13** and **OPEN-14** as the reason.
- This is what makes the staging API safe despite the unanswered access
  questions: it is **unreachable from the network by construction, not by
  policy.** OPEN-13 and OPEN-14 remain unanswered; this build neither answers
  them nor depends on their answers.

### 20.11 Authentication — deliberately minimal and temporary `[NEW]`

- A **single static key** `KB_API_KEY` (from `.env`, §14.2) is sent in the
  **`X-API-Key`** request header.
- A missing or wrong key returns the documented `401`, produces **no answer**,
  and **still writes a Tier 1 row** (outcome `error`, `error_type` =
  `unauthenticated`).
- **This is NOT the production model.** It is one shared secret with no
  per-caller identity, no revocation, and no audit of who used it. §17 F10 and
  OPEN-13/OPEN-14 supersede it. It exists only so the staging endpoint is not wide
  open to whatever else is running on the machine.

### 20.12 Endpoint, response, and errors `[NEW]`

- `POST /v1/answer`, `Content-Type: application/json`.
- **Request:** `{ "workspace": "<workspace_id>", "question": "<text>", "model":
  "<model_id>" }` (`model` optional). `workspace` is the **id**, never the name.
- **Response:** `{ "answer": "<text>", "sources": [ { "document": "...",
  "section": "...", "page": null } ] }`. `sources` is the retrieved set (§20.3);
  `page` is `null` because the stored chunk record has no page field — the format
  does not currently support it. **No `grounded` flag** (OPEN-15); an empty
  `sources` list is the only signal.
- **Empty retrieval** → the documented refusal with `sources: []`, no model call,
  no fabrication (§20.5).
- **Errors** use the §20.6 table **minus `rate_limited`**: `400 invalid_request`,
  `404 workspace_not_found`, `401 unauthenticated`, `503 model_unavailable`,
  `502 provider_error`, `413 request_too_large`. No stack traces.

### 20.13 Deliberately not built in staging `[NEW]`

- **No rate limiting.** A54 remains the production requirement; on localhost with
  one caller it is not needed.
- **No per-caller identity or membership mapping.** One key, one everything.
- **No Tier 2 logging.**
- **No page-number capture** (see §20.12) — that would be an ingestion change and
  a corpus re-processing.
- No conversation persistence for API calls.

**Acceptance criteria:** A48–A62 (§10).

---

## 21. Build sequencing for logging, API, and dashboard

Decided 2026-09-14. **This section carries no acceptance criteria**; it records the
order and the reasoning so it is not reopened later.

1. **§19 — activity logging, first.** A service that cannot be measured,
   troubleshot, or calibrated must not be exposed to other systems. Logging first
   means the API (§20) is born observable: every API call lands in Tier 1 from its
   first request, and the refusal rate is available from day one.
2. **§20 — service interface, second.** Built on top of the logging, so its
   behaviour is recorded and auditable from the start.
3. **The monitoring dashboard — last, and deliberately not specified yet.**
   Designing a dashboard before real log data exists means guessing which figures
   matter. The plan is: build the logging, run it, and see which number is
   repeatedly looked up. **A dashboard spec is deferred until then.**

Note on naming: §17's F11 as listed is the in-app user guide; the monitoring
dashboard is the adjacent deferred item the owner has in mind. It is neither built
nor specified here.

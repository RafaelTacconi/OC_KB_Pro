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

`tests/offline_retrieval_eval.py` already implements the right shape of test: per question, did the expected source appear in top-5, under lexical / semantic / hybrid. It is currently hardcoded to `DEFAULT_WORKSPACE_ID` and has an empty `QUESTION_SET`.

**Change required `[DERIVED]`:** accept `workspace_id` as a CLI argument rather than importing the constant, so it can be run per Workspace.

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

---

## 11. Open questions

Consolidated. Each must be answered by the project owner; none should be resolved by the implementing agent alone.

| # | Question | Interim behaviour | Why it matters |
|---|---|---|---|
| **OPEN-1** | Where is spec v2? Section references throughout the code are unverifiable without it. | Treat the code's docstrings as the authority. | This document may contradict v2 in ways nobody can currently detect. |
| **OPEN-2** | Is the `call_model(prompt, model_id)` widening of constraint C4 approved? Are the `provider_model_name` slugs and the 256k context figures in `models/registry.py` correct? | **Updated, not closed, by Addendum A (§14).** The widening is now confirmed — §14.4 mandates `call_model(prompt, model_id) -> str` stays as the single call site with an unchanged signature, and real slugs / base URL / key are supplied via `.env` (§14.3). What remains open: confirming each model's real `context_window_tokens` against the actual endpoint. | The registry's context-window numbers feed `fits_in_context()`. Wrong numbers mean a wrong guard. |
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

---

## 12. Explicitly out of scope

Do not build these. They are not in the draft or the brief, and adding them would exceed the PoC's stated boundaries.

- Authentication, SSO, user invitation, user removal, password handling (constraint C6).
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

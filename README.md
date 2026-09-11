> **Read `START_HERE.md` and `SPEC.md` first.**
> This README documents the original draft build. `SPEC.md` is the current
> specification and supersedes this file wherever the two disagree — most
> notably, the "single fixed Workspace" model described below is replaced by
> multiple Workspaces and multiple Chats per Workspace (SPEC.md §5 and §6).

# Workspace PoC — draft implementation

Draft scaffold for the Internal AI Workspace Application spec (v2), covering
Sections 5–11: data model, ingestion, hybrid retrieval, prompt assembly, and
the Streamlit UI — plus a **multi-model selector**, which extends spec
constraint 4 (Section 5) to support choosing among several ~256k-context
models rather than one hardcoded model.

## Run it

```bash
pip install -r requirements.txt --break-system-packages   # or use a venv
cp .env.example .env        # fill in OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL_*
streamlit run app.py
```

On first launch, `config.bootstrap()` creates the SQLite schema (WAL mode,
Section 6.1), seeds the fixed test-user list, and creates one default
Workspace with two example tasks (`/summarize-policy`, `/find-procedure`).

**Model endpoint (spec §14 / Step 2b):** `models/router.py::call_model()` is
a real OpenAI-compatible adapter. It reads `OPENAI_BASE_URL`, `OPENAI_API_KEY`,
and the `OPENAI_MODEL_*` slugs from `.env` (copied from the committed
`.env.example`). With no `.env` the app starts and runs, but chat shows a
clear "no model configured" message until you fill one in; Manage and
ingestion keep working either way. Those are the only real values that change
between deployments — everything else the user sees (model names, notes,
context windows) lives in `models/registry.py`.

## What's been verified in this sandbox

- **Schema + WAL mode**: confirmed `journal_mode=wal`, `busy_timeout=8000`,
  and foreign-key enforcement are active on every connection.
- **FTS5 + Porter stemming**: confirmed "escalating" matches text containing
  "escalated" (stemming works); confirmed it does **not** do synonym
  matching (per spec Section 8.1 — this is why hybrid retrieval exists).
- **Parsers**: DOCX heading-based sectioning and XLSX sheet-to-markdown
  rendering both verified against synthetic files. `unstructured` wasn't
  installed in this sandbox, so the DOCX test exercised the pure-Python
  fallback path (`python-docx`) automatically — confirms the fallback
  actually works, not just that it's there.
- **Full ingestion pipeline**: parse → chunk → embed → index → FTS-sync,
  run end-to-end against a real SQLite file, with `sentence-transformers`
  embedding calls stubbed (this sandbox has no network access to
  huggingface.co to download the actual model weights — see note below).
  Confirmed `sources.status` correctly reaches `'indexed'`, chunks carry the
  expected `token_count` and 384-dim (1536-byte) embeddings, and `chunk_text`
  respected section boundaries.
- **`delete_source`**: confirmed it removes the source row, its chunks, and
  the matching FTS rows — satisfies acceptance criterion #9.
- **`lexical_search`**: confirmed a real query ("who can approve deviations")
  correctly retrieves the "Approval Authority" chunk via FTS.
- **Chunking + prompt-assembly unit tests** (`tests/test_chunking_and_prompt.py`):
  7/7 passing — target-size splitting, zero overlap, the oversized-paragraph
  edge case, embedding-excerpt length, fixed prompt assembly order (Section
  9.1), and the `MAX_RETRIEVED_TOKENS` budget cutoff.
- **Failure-path behavior**: when the embedding model genuinely couldn't be
  reached (no network route to huggingface.co in this sandbox),
  `ingest_source()` correctly caught the exception and wrote it to
  `sources.error_message` / `status='failed'` rather than crashing — this is
  exactly the "do not fail silently" behavior the spec requires (Section
  7.2), and it's a good example of the error path actually firing in practice.

**Not runnable in this sandbox** (needs real endpoint values in `.env` and
unrestricted network to huggingface.co for the embedding model download): the
live chat round-trip through `call_model()`, and a real (non-stubbed)
`sentence-transformers` embedding pass. Both are wired and unit-tested at the
logic level; only the actual external calls are unverified here.

## Files

```
app.py                          Streamlit entry point (test-user "login", routing)
config.py                       Fixed test-user list, seed data (constraint 6)
db.py                           SQLite schema + WAL-mode connection helper (Section 6.1)
ingestion/
  parsers.py                    PDF/DOCX/XLSX -> sections (unstructured + fallback)
  chunking.py                   Paragraph-based chunker, ~350-500 tokens, no overlap
  embedding.py                  Local sentence-transformers wrapper
  pipeline.py                   ingest_source() / delete_source() — the ONLY
                                 public entry points (Section 7.5)
retrieval/
  hybrid_search.py              lexical_search, semantic_search, hybrid_search (RRF)
models/
  registry.py                   Selectable model list + metadata (NEW: multi-model)
  router.py                     call_model(prompt, model_id) — single call site
  context_budget.py             MAX_RETRIEVED_TOKENS vs. actual model context window
prompting/
  assemble.py                   build_prompt() — the one place prompts get built
ui/
  chat_view.py                  Chat + model picker + task picker (Section 10.2/10.3)
  owner_view.py                 Knowledge/Instructions/Prompts/Summary tabs (10.1)
tests/
  test_chunking_and_prompt.py   Fast unit tests, no DB/ML deps
  offline_retrieval_eval.py     Section 11a sanity-check harness (fill in real Qs)
```

## Design notes worth flagging back to the spec owner

1. **Multi-model selection vs. constraint 4.** The spec's constraint 4 says
   "one model is used in the PoC" with a thin `call_model(prompt) -> str`
   abstraction. Supporting model choice required widening the signature to
   `call_model(prompt, model_id)`, backed by a small registry
   (`models/registry.py`). The "thin abstraction, no scattered SDK calls"
   *intent* of constraint 4 is preserved — there's still exactly one function
   any caller uses — but this is a real, deliberate deviation from the literal
   text and should be confirmed with whoever owns the spec.
2. **256k context windows and the 3000-token retrieval budget.** These are
   independent by design (see `models/context_budget.py`'s docstring) — a
   much larger context window is not a reason to retrieve more/larger chunks
   without evidence from Section 11a that it improves answers. Flagging this
   explicitly so it isn't "fixed" by someone bumping `MAX_RETRIEVED_TOKENS`
   to use more of the window without re-running the offline eval.
3. **Context-window figures in `models/registry.py` are still unconfirmed.**
   The 256k figure is carried from the owner's original note; `fits_in_context()`
   uses it as the safety guard, so confirm each model's real window against the
   actual endpoint once the `.env` slugs are live (`SPEC.md` §11 OPEN-2,
   updated not closed). Since Step 2b, the slugs themselves live in `.env`
   (per-table split in `SPEC.md` §14.3), not in this file.

# AGENTS.md

Streamlit proof-of-concept: an internal AI Workspace where an Owner uploads documents and
users ask questions grounded in them via hybrid retrieval (SQLite FTS5 + local embeddings).

This file is loaded automatically at the start of every session. It is deliberately short —
the authority is `SPEC.md`.

## Read these first, in this order

1. `START_HERE.md` — how to work on this project.
2. `SPEC.md` — **the specification. The authority. Read it in full before writing code.**
3. `state.md` — where the work stands right now and what to do next.
4. `memory.md` — decisions and discoveries from earlier sessions.

`README.md` is the original draft's build notes. Useful background, superseded by `SPEC.md`
wherever the two disagree.

## Commands

```bash
pip install -r requirements.txt --break-system-packages   # or use a venv
python -m pytest tests/ -q                                # run before and after every step
streamlit run app.py                                      # chat will fail until Step 1 is done
```

**The untouched baseline is `7 passed, 1 failed`.** The failure —
`tests/test_spec_v3_regressions.py::test_oversized_chunk_does_not_discard_smaller_relevant_chunks`
— is intentional. It is acceptance criterion A14 in executable form and defines "done" for
`SPEC.md` §7.2. Never delete, weaken, or skip it.

## Hard rules

1. **Never resolve an `[OPEN]` item yourself.** `SPEC.md` §11 lists ten unanswered questions.
   Where an interim behaviour is given, apply exactly that. Where none is, stop and ask. Do not
   substitute a reasonable-sounding default.
2. **Follow the build order in `SPEC.md` §9.** Steps 1–2 are blocking defect fixes and depend
   on nothing. Do not start features first.
3. **Respect the module boundaries (`SPEC.md` §8).** `ui/` never imports a parser, chunker,
   embedder, or provider SDK. `ingestion/`, `retrieval/`, `prompting/`, `models/` never import
   Streamlit. All prompts are built in `prompting/assemble.py`. All database access goes
   through `db.get_connection()` / `db.transaction()`. No network call or file parse inside a
   `with transaction()` block.
4. **Do not tune retrieval.** `top_k`, `MAX_RETRIEVED_TOKENS`, `rrf_k`, `candidate_pool`, and
   chunk-size targets are fixed until the offline evaluation in `SPEC.md` §9.3 says otherwise.
5. **Do not refactor beyond the spec.** No renaming modules, no ORM, no vector database, no
   replacing Streamlit. `SPEC.md` §12 lists what is explicitly out of scope.
6. **Maintain the journal as you work** — `memory.md`, `state.md`, `changelog.md`, per
   `SPEC.md` §13. Log an `[OPEN]` item the moment you hit it, not at the end. Before stopping
   for any reason, `state.md` must stand on its own.
7. **NEVER delete the repo `data/` directory.** It holds live runtime state — the SQLite DB
   **and** `data/{workspace_id}/sources/` (the actual uploaded files) — and it is gitignored,
   so deletion is unrecoverable. It has destroyed the owner's corpus three times. The test
   suite tolerates a pre-existing `data/`; a clean DB is achieved with a temp cwd, never by
   deleting `data/`. See `memory.md` "Rejected approaches".

## Environment limits

- The chat loop is real up to the model endpoint: ingestion, retrieval,
  prompt assembly, and the §7.1 error handling all work (Steps 1–2, 2b).
  But `models/router.py` reads `OPENAI_BASE_URL` + `OPENAI_API_KEY` + the
  `OPENAI_MODEL_*` slugs from `.env` (`SPEC.md` §14), and there is no live
  endpoint configured in this repo. A chat turn therefore fails at the model
  call and surfaces the §7.1 inline error — which is the *intended*, tested
  behaviour, not a bug. Copy `.env.example` to `.env` and fill it in to get a
  live answer.
- The embedding model (`all-MiniLM-L6-v2`) downloads from huggingface.co on first use. Without
  that route, ingestion fails and writes the error to `sources.error_message`. That is the
  intended behaviour, not a bug.
- Answer quality cannot be assessed without real documents. Do not claim it has been.

## Do not run `/init`

It would rewrite this file from a scan of the codebase and lose the rules above.

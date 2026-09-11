# START HERE — instructions for the implementing agent

## What this package is

A **working baseline** of the Workspace PoC plus a specification for the next round of changes.

- `SPEC.md` — **the authority.** Read it in full before writing any code.
- `state.md` — where the work currently stands. Read this second; it tells you what to do next.
- `memory.md` — decisions and discoveries carried forward from earlier sessions.
- `changelog.md` — what has shipped so far.
- `README.md` — the original build notes. Useful background, but written before `SPEC.md` and **superseded by it wherever the two disagree** (most notably: the README describes a single fixed Workspace; `SPEC.md` §5 replaces that).
- The code — a known-state baseline. It is **not** bug-free, and that is deliberate: `SPEC.md` §7 documents the defects at file-and-function level, and the code has been left as-is so those references stay verifiable.

## Rules

1. **Do not resolve an `[OPEN]` item yourself.** `SPEC.md` §11 lists ten open questions. Where an interim behaviour is given, implement exactly that and move on. Where none is given, stop and ask. Do not pick a reasonable-sounding default and proceed — the whole point of the tagging system is that these decisions belong to the project owner.
2. **Follow the build order in `SPEC.md` §9.** Steps 1–2 fix blocking defects and depend on nothing. Do not start the new features first.
3. **Preserve the architecture rules in `SPEC.md` §8.** `ui/` never imports a parser, chunker, embedder, or provider SDK. `ingestion/`, `retrieval/`, `prompting/`, `models/` never import Streamlit. All prompts are built in `prompting/assemble.py`. All DB access goes through `db.get_connection()` / `db.transaction()`.
4. **Do not refactor beyond the spec.** No renaming modules, no swapping Streamlit for something else, no introducing an ORM, no adding a vector database. `SPEC.md` §12 lists what is explicitly out of scope.
5. **Do not tune retrieval parameters.** `top_k`, `MAX_RETRIEVED_TOKENS`, `rrf_k`, `candidate_pool`, and chunk-size targets are fixed until the offline evaluation (§9.3) says otherwise.
6. **Keep the journal current.** `memory.md`, `state.md`, and `changelog.md` are maintained as you work, not written up at the end — `SPEC.md` §13 defines what goes in each and when. Write the `memory.md` entry for an `[OPEN]` item the moment you hit it, before continuing. Before you stop for any reason, `state.md` must stand on its own: a fresh session with no memory of this one should be able to resume from it alone.
7. **Report what you did not do.** At the end, list every `[OPEN]` item you hit and the interim behaviour you applied. This should be a summary of `memory.md`, not new information.

## Tests

```bash
pip install -r requirements.txt --break-system-packages   # or use a venv
python -m pytest tests/ -q
```

Expected on the untouched baseline: **7 passed, 1 failed.**

The failure is `tests/test_spec_v3_regressions.py::test_oversized_chunk_does_not_discard_smaller_relevant_chunks`. It is red on purpose — it is acceptance criterion A14 in executable form, and it defines "done" for the blocking defect in `SPEC.md` §7.2. A one-line change (`break` → `continue` in `prompting/assemble.py`) turns it green without breaking the other seven. Do not delete it, weaken it, or skip it.

## Things you cannot verify here

- `models/router.py::call_model()` is real but reads its endpoint config
  (`OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL_*`) from `.env` — which is
  not committed here. Copy `.env.example` to `.env` and fill it in to reach a
  live model; without it every chat turn fails at the model call and surfaces
  the §7.1 inline error, which is the intended, tested behaviour (SPEC.md §14,
  Step 2b).
- The embedding model (`all-MiniLM-L6-v2`) downloads from huggingface.co on first use. If the environment has no network route there, ingestion will fail and write the error to `sources.error_message` — the intended behaviour, not a bug.
- End-to-end answer quality cannot be assessed without real documents. Do not claim it has been.

## Suggested kickoff message

> This repository contains a Streamlit PoC and a specification, `SPEC.md`.
>
> Read `START_HERE.md` first, then `SPEC.md` in full, then the code. Implement the spec following the build order in §9, starting at Step 1.
>
> `SPEC.md` tags every requirement with its provenance. Items tagged `[OPEN]` are unresolved questions — implement the stated interim behaviour where one is given, and stop and ask where none is. Do not invent answers to them.
>
> Work in small commits, one build-order step per commit. Run `python -m pytest tests/ -q` before and after each step. The baseline is 7 passed, 1 failed; the failing test is intentional and must be green by the end of Step 1.
>
> Maintain `memory.md`, `state.md`, and `changelog.md` as you go, per `SPEC.md` §13 — they are seeded with the current state, so follow the format already there. Log every `[OPEN]` item you hit in `memory.md` at the moment you hit it. Update `state.md` at the start and end of every step, and before you stop for any reason.
>
> When you finish, report: which build-order steps you completed, which `[OPEN]` items you encountered and what interim behaviour you applied, and anything in the spec you believe is wrong or unimplementable.

## Changes made to the original archive

Only two files were added and two were touched non-functionally. **No application code was modified**, so every file-and-line reference in `SPEC.md` §7 still points at the real thing.

| File | Change |
|---|---|
| `SPEC.md` | Added. |
| `START_HERE.md` | Added (this file). |
| `memory.md`, `state.md`, `changelog.md` | Added, seeded with the current state (`SPEC.md` §13). |
| `AGENTS.md` | Added. Auto-loaded by opencode at the start of every session. |
| `tests/test_spec_v3_regressions.py` | Added. Intentionally failing — see above. |
| `requirements.txt` | Added `pytest` under a dev-dependencies comment. |
| `README.md` | Added a short header noting that `SPEC.md` supersedes it. No other edits. |

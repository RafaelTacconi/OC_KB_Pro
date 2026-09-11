# state.md — where the work is right now

Overwritten in place on every update. Keep under one page. Rules: `SPEC.md` §13.3.
History belongs in `changelog.md`, not here.

**Last updated:** 2026-09-11 — Step 6 complete.

---

## Current step

**Step 7 — cleanup (next).** §7.6 (stale task selection sends an untagged
message — pick option (a): clear + note inline), §7.7 (FTS deletion ordering
comment at `ingestion/pipeline.py::delete_source`), §7.8 (docs + duplication
cleanup: `estimate_tokens` dedupe, `ROLE_PILL_MAP` dedupe, `models/registry.py`
docstring fix, `static/fonts/README.md` reference, brittle-alignment-hack
already done in Step 2b, `st.success`-then-`rerun` toasts, raw exception text
prefix).

## Progress

| Step | Description | Status |
|---|---|---|
| 1 | Unblock the app — fix §7.2 (`break` → `continue` + test) and §7.1 (error handling, message persistence) | **Done** |
| 2 | Resilience — §7.3 lexical degrade path, §7.4 delete confirmations | **Done** |
| 2b | Provider config and key expiry — §14: `.env`, adapter, `models/credentials.py`, sidebar warning | **Done** |
| 3+4 | Schema + multi-Chat (landed together) | **Done** |
| 5 | Multi-Workspace — selector, create form, membership, branding fix | **Done** |
| 6 | Visibility — grounding status, model attribution in history | **Done** |
| 7 | Cleanup — §7.6, §7.7, §7.8 | Not started — **§7.8 "brittle alignment hack" already done in Step 2b** (the `margin-top: 1.6rem` in `ui/chat_view.py` model-note was removed when that line was touched — do not redo or skip around it) |
| 8 | Evaluate — §9.3 offline retrieval evaluation | Not started (needs real documents) |

## Blocked on

Nothing blocks Step 7. It has no `[OPEN]` dependency.

**OPEN-3/4/5/7 interim applied** (`memory.md`). **OPEN-2** updated not closed.
**OPEN-12** interim implemented. **OPEN-11** answered (OpenAI-compatible proxy).
Deferred decision resolved: degraded answers are NOT persisted with a marker
(`memory.md`, agent decision 2026-09-11).

## Test status

```
python -m pytest tests/ -q
51 passed in 19.24s
```
Run on 2026-09-11 after Step 6. Added `tests/test_grounding_and_attribution.py`
(5: A17 as a Member, §5.2.4 indexed-count caption, failed-notes Owner-only,
§7.5 attribution display-name + unknown-id fallback). No `data/` at the repo
root after the suite (enforced by conftest).

## Next action

Start Step 7. (1) §7.6: in `ui/chat_view.py`, when a Task is selected and the
user submits via the free-text input, clear the Task selection and note inline
that the Task was not applied — option (a), preferred. (2) §7.7: add the
ordering comment at `ingestion/pipeline.py::delete_source` stating chunks_fts
rows must be deleted before chunks rows. (3) §7.8: dedupe `estimate_tokens`
(define once in `models/context_budget.py`, import in `ingestion/chunking.py`),
move `ROLE_PILL_MAP` to `ui/pills.py` and import in `app.py` + `ui/owner_view.py`,
fix `models/registry.py`'s docstring (points at `ui/model_picker.py`; the picker
is in `ui/chat_view.py::_render_model_picker`), resolve the `.streamlit/config.toml`
`static/fonts/README.md` reference, replace the `st.success`-then-`rerun` toasts
in `ui/owner_view.py` with a session flag or drop them, and prefix `sources.error_message`
display with a short human-readable line. Run `python -m pytest tests/ -q` before
and after.
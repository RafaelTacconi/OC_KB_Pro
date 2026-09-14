# OC_KB_Pro

OC_KB_Pro answers questions strictly from a defined set of documents. Every answer
carries the sources it was drawn from, and when the documents do not contain the
answer it says so plainly instead of guessing. **The refusal is the point of the
system, not a footnote to it.**

This README is for someone who has never seen the project: a colleague, a
reviewer, or a future maintainer. `SPEC.md` is the authority for behaviour — if
this file and `SPEC.md` disagree, `SPEC.md` wins.

## What it is

OC_KB_Pro is a question-answering service for a fixed body of documents. You
group documents into a **Workspace** (for example, one Workspace per policy
area), ask a question, and get an answer built only from those documents, with
the source files and sections cited.

If the documents do not answer the question, the correct result is the refusal:
"I can't determine this from the available documents." This is the central
property of the system — it is designed to refuse rather than guess. An answer
that cannot be traced to a source is a defect, not a feature.

It is a proof of concept, not a production service. See **Current status** and
**Known limitations** below.

## How it works

1. **Documents are uploaded into a Workspace and indexed.** Supported formats are
   PDF, DOCX and XLSX. Indexing splits each document into passages and stores them
   for search. (Content inside images is not read — see Known limitations.)
2. **A question searches only that Workspace and retrieves a small number of
   relevant passages.** Search combines keyword matching with semantic
   similarity, and the Workspace boundary is enforced: documents from another
   Workspace can never be retrieved.
3. **Only those passages are sent to the model — never the whole knowledge
   base.** This is worth stating plainly, because almost everyone assumes the
   model is given the full document set. It is not. Only the handful of retrieved
   passages, the Workspace's instructions, and the question are sent.
4. **The model answers from those passages alone and cites its sources.** It is
   instructed to use nothing else, and to refuse when the passages do not support
   an answer.

The model never sees the full document set.

## Scope

**OC_KB_Pro owns:**

- Workspace and document isolation
- Document ingestion and indexing
- Retrieval
- Grounded answer generation
- Source and citation selection
- "I can't determine this from the available documents" behaviour
- Workspace-specific instructions
- Access control around the knowledge base
- Eventually, an API for other applications (§20)

**The calling task/workflow system owns:**

- The actual case or task
- Customer, account and transaction data
- Workflow state
- Business-specific logic
- Deciding which question to ask OC_KB_Pro
- Deciding what to do with the answer
- Executing actions
- Human approval
- Recording the final outcome

```
                 ┌──────────────────────────┐
                 │   Task / Workflow App    │
                 │                          │
                 │  Case context            │
                 │  Business logic          │
                 │  Workflow                │
                 │  Actions                 │
                 │  Human approval          │
                 └────────────┬─────────────┘
                              │
                    "What does the
                     procedure require?"
                              │
                              ▼
                 ┌──────────────────────────┐
                 │        OC_KB_Pro         │
                 │                          │
                 │  Workspace               │
                 │  Documents               │
                 │  Retrieval               │
                 │  Grounded answer         │
                 │  Citations               │
                 └──────────────────────────┘
```

Another system asks a clear question, this service searches the right Workspace,
and returns an answer with its sources. It does not hold the case and it does not
decide what happens next.

## Current status

A proof of concept.

- Build Steps 1–7 of `SPEC.md` §9 are complete, and Step 8 (the retrieval
  evaluation, §9.3) has been run.
- **Step 8 result:** with the same questions, the focused Workspaces retrieved
  the expected source in the top 5 **15 times out of 15**; the single mixed
  Workspace scored **14 out of 15**. That is a one-question difference on a
  15-question set — **too small a sample to conclude that separating documents by
  Workspace improves retrieval.** The measured benefit of separation is the
  per-Workspace **instructions**, not retrieval. No retrieval setting was changed
  as a result.
- The owner has run the pipeline by hand against a live model endpoint on their
  own machine — the figure above comes from that run. Automated tests never call
  the live model.

## Known limitations

- **No authentication.** Users are selected from a fixed dropdown (constraint C6).
- **No conversation memory.** Follow-up questions do not work; each question is
  answered independently (OPEN-3).
- **Content inside images is not read or indexed.** The Owner sees an image-count
  warning only (§15.1).
- **No cross-Workspace search** (OPEN-10).
- **No way to delete a Workspace or a Chat** (OPEN-6, OPEN-8).
- **No logging yet** (§19 is specified but not built).
- **No API yet** (§20 is specified but not built).
- **Heading detection in citations is a shape heuristic** validated only against
  the synthetic test corpus, not against real documents (A29 caveat).

## Running it

**Start the app from a terminal with the virtual environment active.** Launching
it any other way (a desktop shortcut, an IDE "Run" button) can cause Streamlit to
re-exec to the base Python interpreter, which does not have
`sentence-transformers` installed. When that happens, uploads fail silently while
the interface still looks fine.

```bash
# Setup (once)
pip install -r requirements.txt --break-system-packages   # or use a venv
cp .env.example .env        # fill in OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL_*

# Start — from a terminal, with the venv active
streamlit run app.py
```

- On first launch, `config.bootstrap()` creates the SQLite schema and seed data.
- With no `.env`, the app starts and Manage and ingestion still work, but chat
  shows a clear "No AI model is configured" message and the send controls are
  disabled until you fill one in.
- The embedding model (`all-MiniLM-L6-v2`) downloads from huggingface.co on first
  use. Without a network route to it, ingestion fails and writes the error to the
  Source row rather than crashing.

## Where to look

- `SPEC.md` — the authority for behaviour; every claim in this README traces to it.
- `memory.md`, `state.md`, `changelog.md` — the project journal: decisions and
  discoveries, current position, and what actually shipped.
- `ACCEPTANCE_MATRIX.md` — maps each acceptance criterion (A-number) to the test
  or evidence that proves it.
- `GROUNDING_REGRESSION.md` — the hand-run grounding regression tests (no
  automated test may call the live model).
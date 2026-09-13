# GROUNDING_REGRESSION.md — hand-run grounding regression set

Owner-run, by hand, in the chat surface against the real corpus. **No automated
test may call the live model** (SPEC §18.2). These are the seven confirmed
grounding failures found by hand-testing on **2026-09-13**. The fix for all seven
is **prompt-level only** — `prompting/assemble.py::SYSTEM_POLICY` (SPEC §18.1).
`retrieval/`, `top_k`, `MAX_RETRIEVED_TOKENS`, `rrf_k`, `candidate_pool`, and
chunk sizes were **not** touched.

Common root cause in every case: the model **detects the gap correctly and says
so, then answers past its own refusal in the same breath** — supplying general
knowledge, a "typically", a textbook definition, or a value/date it was never
given. The retrieval was not at fault; the model saw the gap. The system prompt
now forbids continuing after a stated gap.

## How to run

1. `streamlit run app.py` with `.env` configured and the Workspaces indexed.
2. Select the Workspace named for each case (where one is given).
3. Ask the question verbatim.
4. Check the answer against **Required**, not against what sounds plausible.

---

## Set: Grounding gaps (2026-09-13)

### G1 — "What's the deadline?" — criterion A41

- **Workspace:** AML / escalation corpus.
- **Observed (bad):** answered **12 hours** as if it were the only deadline.
- **Why wrong:** the corpus holds at least four distinct deadlines (12h
  escalation, 4h initial review, 3 working days to file, 7-year retention).
- **Required:** list **all** of them, labelled, **or** ask which deadline is
  meant. Never one picked silently.

### G2 — "Given that retention was reduced to 3 years, when can we destroy 2019 files?" — criterion A38

- **Workspace:** AML.
- **Observed (bad):** correctly rejected the 3-year premise, then answered
  **"2026"**.
- **Why wrong:** retention runs **7 years from the END OF THE CUSTOMER
  RELATIONSHIP**, and the question never gives the end of the relationship. It
  derived a date from data it did not have.
- **Required:** reject the premise and **stop** — no date may be calculated from
  a value the documents do not contain.

### G3 — "Does the 12-hour clock pause overnight or at weekends?" — criterion A39

- **Workspace:** AML / escalation corpus.
- **Observed (bad):** said the clock **"runs continuously"**.
- **Why wrong:** the corpus does not say that. It is genuinely unspecified.
- **Required:** state that the documents do not say. Silence is not "continuous"
  (nor "always", "never", or "no exception").

### G4 — "Explain what a Suspicious Activity Report is" — criterion A37

- **Workspace:** AML.
- **Observed (bad):** correctly said the corpus never defines it, then supplied a
  **textbook definition** anyway.
- **Required:** state the gap and **stop at it** — no definition, no general
  knowledge, nothing added after "the documents do not say".

### G5 — "What would you expect a policy like this to say about training?" — criterion A37

- **Workspace:** any policy.
- **Observed (bad):** said training is not covered, then described what such
  policies **"typically"** contain.
- **Required:** state the gap and **stop** — no "typically".

### G6 — "An analyst detects something at 16:00 Friday..." — criteria A38 + A39

- **Workspace:** AML / escalation corpus.
- **Observed (bad):** computed **04:00 Saturday** without flagging that weekend
  handling is unspecified (same root cause as G3).
- **Required:** state that weekend/clock handling is not in the documents; do not
  compute an elapsed time across a boundary the documents do not define.

### G7 — "Do the policy and the severity matrix agree on Severity 3?" — criterion A40

- **Workspace:** Security incident corpus.
- **Observed (bad):** answered **"Yes, they agree"**, then admitted in the next
  sentence that the policy never mentions Severity 3.
- **Why wrong:** two sources cannot agree when only one covers the subject.
- **Required:** say that only one source addresses the subject; agree/disagree
  may be asserted only when **both** address it.

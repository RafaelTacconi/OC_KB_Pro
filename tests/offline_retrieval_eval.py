"""
offline_retrieval_eval.py — Section 11a offline sanity check.

NOT a formal RAGAS/LLM-judged evaluation (explicitly not required for this
PoC's size). A hand-checked "did the right chunk show up in top-5, yes/no,
per method" pass — matches acceptance criterion #6/#7's own wording.

Usage:
    python -m tests.offline_retrieval_eval <workspace_id> <set>

      <workspace_id>  the Workspace to evaluate against
      <set>           which question set to run: aml | hr | sec | all

    e.g. python -m tests.offline_retrieval_eval aml-workspace aml
         python -m tests.offline_retrieval_eval 524bf0ec... all

Read the printed table, then the MISSES block (question, expected source, and
the five files actually retrieved), and the top-5 hit rate (SPEC §9.3).

The harness refuses to run while semantic retrieval is unavailable: it does
NOT silently degrade to lexical-only results, because comparing identical
rows would falsely suggest hybrid adds nothing (SPEC.md §7.3).

The negative control (a question with no expected source) is deliberately NOT
in these sets — the harness would score correct refusal as a miss. Check it by
hand in chat.
"""

from __future__ import annotations

from retrieval.hybrid_search import hybrid_search, lexical_search, semantic_search

# --- Financial Crime / AML -------------------------------------------------

AML_QUESTIONS = [
    {"question": "How quickly must suspicious activity be escalated?",
     "expected_source_substring": "AML_Policy.pdf"},
    {"question": "Who can approve a deviation from the suspicious activity escalation timeline?",
     "expected_source_substring": "AML_Policy.pdf"},
    {"question": "How long does an analyst have to complete the initial review of an alert?",
     "expected_source_substring": "AML_Escalation_Procedure.docx"},
    {"question": "What is the transaction threshold for a high-risk customer using correspondent banking?",
     "expected_source_substring": "AML_Thresholds.xlsx"},
    {"question": "Can a line manager sign off an exception to the reporting deadline?",
     "expected_source_substring": "AML_Policy.pdf"},
    {"question": "What is the biggest single payment a risky client can make before extra checks kick in?",
     "expected_source_substring": "AML_Thresholds.xlsx"},
]

# --- People / HR -----------------------------------------------------------

HR_QUESTIONS = [
    {"question": "How quickly must a grievance escalation be acknowledged?",
     "expected_source_substring": "HR_Grievance_Policy.pdf"},
    {"question": "How many informal attempts are needed before a formal panel is convened?",
     "expected_source_substring": "HR_Grievance_Policy.pdf"},
    {"question": "What happens if nobody responds to a leave request?",
     "expected_source_substring": "HR_Leave_Procedure.docx"},
    {"question": "Who approves unpaid leave?",
     "expected_source_substring": "HR_Approval_Matrix.xlsx"},
]

# --- IT Security -----------------------------------------------------------

SEC_QUESTIONS = [
    {"question": "How quickly must a Severity 1 incident be escalated?",
     "expected_source_substring": "Security_Incident_Policy.pdf"},
    {"question": "When does an incident count as Severity 1?",
     "expected_source_substring": "Security_Incident_Policy.pdf"},
    {"question": "Who decides on regulatory notification during an incident?",
     "expected_source_substring": "Incident_Response_Procedure.docx"},
    {"question": "How quickly is a war room convened for a Severity 1?",
     "expected_source_substring": "Severity_Thresholds.xlsx"},
    {"question": "Who has the final say on telling the regulator about a breach?",
     "expected_source_substring": "Incident_Response_Procedure.docx"},
]

QUESTION_SETS: dict[str, list[dict]] = {
    "aml": AML_QUESTIONS,
    "hr": HR_QUESTIONS,
    "sec": SEC_QUESTIONS,
    "all": AML_QUESTIONS + HR_QUESTIONS + SEC_QUESTIONS,
}

# Back-compat alias: the combined set.
QUESTION_SET = QUESTION_SETS["all"]

TOP_K = 5


def _found(chunks: list[dict], expected_substring: str) -> bool:
    return any(expected_substring.lower() in c["display_name"].lower() for c in chunks)


def run_eval(workspace_id: str, questions: list[dict] | None = None) -> None:
    questions = QUESTION_SET if questions is None else questions
    if not questions:
        print("Question set is empty — nothing to evaluate.")
        return

    rows = []
    for item in questions:
        q = item["question"]
        expected = item["expected_source_substring"]

        lex = lexical_search(q, workspace_id, top_k=TOP_K)
        sem = semantic_search(q, workspace_id, top_k=TOP_K)
        hyb, degraded = hybrid_search(q, workspace_id, top_k=TOP_K)
        if degraded:
            raise RuntimeError(
                "Semantic retrieval is unavailable (the embedding model did not "
                "load). The evaluation harness refuses to compare lexical-only "
                "hybrid results — a silent fallback would make hybrid and "
                "lexical-only produce identical rows and could falsely suggest "
                "hybrid adds nothing (SPEC.md §7.3 / §9.3)."
            )

        rows.append(
            {
                "question": q,
                "expected": expected,
                "lexical_hit": _found(lex, expected),
                "semantic_hit": _found(sem, expected),
                "hybrid_hit": _found(hyb, expected),
                "retrieved": [c["display_name"] for c in hyb],
            }
        )

    print(f"{'Question':<60} {'Lexical':<10} {'Semantic':<10} {'Hybrid':<10}")
    print("-" * 90)
    hybrid_worse_count = 0
    for r in rows:
        print(
            f"{r['question'][:58]:<60} "
            f"{'Y' if r['lexical_hit'] else '.':<10} "
            f"{'Y' if r['semantic_hit'] else '.':<10} "
            f"{'Y' if r['hybrid_hit'] else '.':<10}"
        )
        if r["lexical_hit"] and not r["hybrid_hit"]:
            hybrid_worse_count += 1

    print("-" * 90)
    n = len(rows)
    hits = sum(1 for r in rows if r["hybrid_hit"])
    print(f"Top-5 hit rate (hybrid): {hits}/{n} = {hits / n:.0%}")
    print(
        f"Hybrid underperformed lexical-only on {hybrid_worse_count} question(s). "
        + (
            "This exceeds 'a couple' — revisit the embedding strategy (Section 8.2a) "
            "before running the user-facing comparison."
            if hybrid_worse_count > 2
            else "Within the acceptable range per Section 11a guidance."
        )
    )

    misses = [r for r in rows if not r["hybrid_hit"]]
    print("\nMISSES (hybrid top-5):")
    if not misses:
        print("  (none)")
    for r in misses:
        print(f"- Q: {r['question']}")
        print(f"  expected: {r['expected']}")
        print(f"  retrieved: {r['retrieved']}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3 or sys.argv[2] not in QUESTION_SETS:
        print(
            "Usage: python -m tests.offline_retrieval_eval <workspace_id> <set>\n"
            "  <set> is one of: " + " | ".join(QUESTION_SETS) + "\n"
            "e.g.   python -m tests.offline_retrieval_eval aml-workspace aml"
        )
        sys.exit(2)

    run_eval(sys.argv[1], QUESTION_SETS[sys.argv[2]])

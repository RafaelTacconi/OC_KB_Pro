"""
offline_retrieval_eval.py — Section 11a offline sanity check.

NOT a formal RAGAS/LLM-judged evaluation (explicitly not required for this
PoC's size). A hand-checked "did the right chunk show up in top-5, yes/no,
per method" pass — matches acceptance criterion #6/#7's own wording.

Usage:
    1. Fill in QUESTION_SET below with real questions and the source file
       each should be answered from (ground truth), after uploading your
       actual test documents through the owner UI.
    2. Run: python -m tests.offline_retrieval_eval
    3. Read the printed table. If hybrid underperforms lexical-only on more
       than a couple of questions, revisit the embedding strategy
       (Section 8.2a) before running the user-facing comparison (Section 11).
"""

from __future__ import annotations

from retrieval.hybrid_search import hybrid_search, lexical_search, semantic_search

# Fill in with real questions against your actual uploaded documents.
# `expected_source_substring` should be a distinctive substring of the
# expected source file's display_name (e.g. "AML_Policy.pdf").
QUESTION_SET: list[dict] = [
    # {
    #     "question": "Can a manager approve this kind of exception?",
    #     "expected_source_substring": "AML_Policy.pdf",
    # },
]

TOP_K = 5


def _found(chunks: list[dict], expected_substring: str) -> bool:
    return any(expected_substring.lower() in c["display_name"].lower() for c in chunks)


def run_eval(workspace_id: str) -> None:
    if not QUESTION_SET:
        print(
            "QUESTION_SET is empty — fill in tests/offline_retrieval_eval.py "
            "with 10-15 real questions before running this (Section 11a)."
        )
        return

    rows = []
    for item in QUESTION_SET:
        q = item["question"]
        expected = item["expected_source_substring"]

        lex = lexical_search(q, workspace_id, top_k=TOP_K)
        sem = semantic_search(q, workspace_id, top_k=TOP_K)
        hyb = hybrid_search(q, workspace_id, top_k=TOP_K)

        rows.append(
            {
                "question": q,
                "lexical_hit": _found(lex, expected),
                "semantic_hit": _found(sem, expected),
                "hybrid_hit": _found(hyb, expected),
            }
        )

    print(f"{'Question':<60} {'Lexical':<10} {'Semantic':<10} {'Hybrid':<10}")
    print("-" * 90)
    hybrid_worse_count = 0
    for r in rows:
        print(
            f"{r['question'][:58]:<60} "
            f"{'✓' if r['lexical_hit'] else '✗':<10} "
            f"{'✓' if r['semantic_hit'] else '✗':<10} "
            f"{'✓' if r['hybrid_hit'] else '✗':<10}"
        )
        if r["lexical_hit"] and not r["hybrid_hit"]:
            hybrid_worse_count += 1

    print("-" * 90)
    print(
        f"Hybrid underperformed lexical-only on {hybrid_worse_count} question(s). "
        + (
            "This exceeds 'a couple' — revisit the embedding strategy (Section 8.2a) "
            "before running the user-facing comparison."
            if hybrid_worse_count > 2
            else "Within the acceptable range per Section 11a guidance."
        )
    )


if __name__ == "__main__":
    from config import DEFAULT_WORKSPACE_ID

    run_eval(DEFAULT_WORKSPACE_ID)

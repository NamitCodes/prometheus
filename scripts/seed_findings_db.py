#!/usr/bin/env python
"""
CLI script: initialize the Findings DB schema (and optionally seed it with
sample reports for local development / demos).

Usage:
    python scripts/seed_findings_db.py
    python scripts/seed_findings_db.py --with-sample-data
"""
from __future__ import annotations

import argparse

from prometheus.findings import repository

_SAMPLE_REPORTS = [
    {
        "question": "Does retrieval-augmented generation reduce hallucination rates in LLMs?",
        "summary": (
            "Evidence across the sampled papers supports a reduction in hallucination "
            "when generation is conditioned on retrieved passages, though effect size "
            "varies with retriever quality."
        ),
        "status": "approved",
        "claims": [
            {
                "statement": "RAG reduces unsupported claims compared to closed-book generation.",
                "confidence_level": 0.8,
                "supporting_evidence_ids": ["sample-1", "sample-2"],
            }
        ],
    },
    {
        "question": "Does hybrid (BM25 + dense) retrieval outperform dense-only retrieval?",
        "summary": (
            "Hybrid retrieval shows consistent gains on keyword-heavy queries; gains "
            "shrink on paraphrase-heavy queries where dense retrieval already excels."
        ),
        "status": "approved",
        "claims": [
            {
                "statement": "Hybrid retrieval improves recall@k on exact-match-sensitive queries.",
                "confidence_level": 0.7,
                "supporting_evidence_ids": ["sample-3"],
            }
        ],
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-sample-data", action="store_true")
    args = parser.parse_args()

    repository.init_db()
    print("Findings DB schema created.")

    if args.with_sample_data:
        for report in _SAMPLE_REPORTS:
            report_id = repository.save_report(report)
            print(f"seeded report {report_id}: {report['question'][:60]}")


if __name__ == "__main__":
    main()

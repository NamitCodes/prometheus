"""
RAGAS-based evaluation of retrieval faithfulness (per proposal, Section 4).

TODO:
  - Build a RAGAS EvaluationDataset from (question, retrieved_chunks, answer)
    triples logged during real runs or a held-out test set
  - Run faithfulness / context_precision / context_recall metrics
  - Wire into CI or a scheduled eval job, log results to LangSmith
"""
from __future__ import annotations


def evaluate_retrieval(samples: list[dict]) -> dict:
    raise NotImplementedError("Phase 5: implement RAGAS evaluation")

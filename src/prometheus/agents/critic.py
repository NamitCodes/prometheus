"""
Critic Agent

Responsibility (per proposal, Section 3):
  Checks the Synthesizer's draft findings for unsupported claims,
  confounds, and small-n issues. Runs an adversarial debate loop against
  the Synthesizer: the Synthesizer cannot finalize a conclusion without
  Critic approval. On rejection, loops back to the Planner or Researcher
  with concrete objections.

TODO:
  - Define def critic_node(state: GraphState) -> GraphState
  - Define the approve/reject decision the LangGraph conditional edge reads
    (e.g. state["critic_verdict"] in {"approve", "reject"})
  - Objection schema: claim_id, issue_type (unsupported | confound | small_n),
    explanation, suggested_fix
  - Guard against infinite debate loops (max rounds, then escalate to human)
"""
from __future__ import annotations

from typing import Any


def critic_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node. Reads state["draft_conclusion"] + state["evidence"],
    writes state["critic_verdict"] and state["objections"]."""
    raise NotImplementedError("Phase 2: implement Critic Agent")

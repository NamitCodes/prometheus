"""
Synthesizer Agent

Responsibility (per proposal, Section 3):
  Drafts the conclusion for a sub-question from the gathered evidence.
  Requires Critic approval to finalize; on rejection, revises the draft
  in light of the Critic's objections (or the loop routes further back to
  Planner/Researcher for more evidence, per the graph's conditional edges).

TODO:
  - Define def synthesizer_node(state: GraphState) -> GraphState
  - Output schema per claim: statement, confidence_level, supporting_evidence_ids
  - Handle "revise" vs "needs more evidence" cases differently
"""
from __future__ import annotations

from typing import Any


def synthesizer_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node. Reads state["evidence"] (+ state["objections"] on a
    revision pass), writes state["draft_conclusion"]."""
    raise NotImplementedError("Phase 2: implement Synthesizer Agent")

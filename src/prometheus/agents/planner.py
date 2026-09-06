"""
Planner Agent

Responsibility (per proposal, Section 3):
  Given a sub-question handed down by the Meta-Orchestrator, decompose it
  further if needed and form one or more *testable* hypotheses that the
  Researcher/Retriever agents can go gather evidence for.

Also the re-entry point when the Critic rejects a finding: the Planner
receives the Critic's objection and reformulates the hypothesis.

TODO:
  - Define the LangGraph node signature: def planner_node(state: GraphState) -> GraphState
  - Prompt: sub-question + prior findings (if a reject loop-back) -> hypotheses list
  - Decide hypothesis schema (id, statement, expected_evidence_type, confidence_prior)
"""
from __future__ import annotations

from typing import Any


def planner_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node. Reads state["sub_question"] (+ state["critic_feedback"]
    on a loop-back) and writes state["hypotheses"]."""
    raise NotImplementedError("Phase 2: implement Planner Agent")

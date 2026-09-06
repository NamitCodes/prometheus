"""
Researcher Agent

Responsibility (per proposal, Section 3):
  Runs the agentic RAG loop: retrieve -> assess -> reformulate. Given a
  hypothesis from the Planner, issues (possibly several rounds of) queries
  against the Retriever Agent, assesses whether the returned evidence
  actually supports/refutes the hypothesis, and reformulates the query if
  the first pass came back thin or off-topic.

TODO:
  - Define def researcher_node(state: GraphState) -> GraphState
  - Loop/termination condition: max retrieval rounds, or "evidence sufficient" check
  - Decide what "assess" means concretely (LLM judgment call on relevance + coverage)
"""
from __future__ import annotations

from typing import Any


def researcher_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node. Reads state["hypotheses"], drives the retrieve/assess/
    reformulate loop via the Retriever Agent, writes state["evidence"]."""
    raise NotImplementedError("Phase 2: implement Researcher Agent")

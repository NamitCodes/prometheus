"""
Sub-Orchestrator graph (one instance per sub-question).

Wires together Planner -> Researcher/Retriever -> Critic <-> Synthesizer
into a LangGraph StateGraph, matching docs/architecture.md:

    Planner --> Researcher --> Retriever --> Critic
    Critic <--> Synthesizer            (debate loop)
    Critic --reject--> Planner | Researcher   (conditional edge)
    Synthesizer --approved--> END (returns to Meta-Orchestrator)

TODO:
  - Define GraphState (TypedDict) shared by all nodes in this file or a
    shared prometheus.graph.state module
  - Build the StateGraph, add_node for each agent in prometheus.agents.*
  - Add the conditional edge on critic_verdict (approve -> synthesizer
    finalizes; reject -> back to planner/researcher per objection type)
  - Add a checkpointer (LangGraph's built-in) for human-in-the-loop pause
    points and time-travel debugging
  - Cap debate-loop rounds; escalate to human if exceeded
"""
from __future__ import annotations

from typing import Any


def build_sub_orchestrator_graph() -> Any:
    """Returns a compiled LangGraph graph for a single sub-question."""
    raise NotImplementedError("Phase 3: build the sub-orchestrator StateGraph")

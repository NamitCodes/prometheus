"""Graph state (new-plan.md section 26)."""
from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class GraphState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    project_id: str

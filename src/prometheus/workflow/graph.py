"""Basic LangGraph workflow (new-plan.md Phase 9):

    START -> agent -> [tool_calls?] -> tools -> agent -> ... -> END

The simplest useful graph: an agent node that can call `knowledge_search`
zero or more times before answering. Citations are extracted from the tool
call results in the message history rather than trusted from the model's
prose (new-plan.md section 28).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from prometheus.config import settings
from prometheus.workflow.state import GraphState
from prometheus.workflow.tools import make_knowledge_search_tool
from prometheus.workflow.web_tools import WEB_TOOLS

SYSTEM_PROMPT = (
    "You are a research assistant with NO built-in knowledge of the user's documents -- "
    "you cannot see, remember, or guess their content. The ONLY way to access them is by "
    "calling the knowledge_search tool, which is a semantic search over document chunks -- "
    "it will NOT contain a ready-made answer to the user's exact question, even when the "
    "question is reasonable (e.g. searching won't turn up a chunk literally titled "
    "'summary'). Your job is to synthesize an answer FROM whatever passages come back, "
    "the same way you would if someone handed you a few relevant excerpts and asked you "
    "to work with them.\n\n"
    "For ANY question that could relate to an uploaded document -- including vague requests "
    "like 'summarize the paper' or 'use the document provided' -- call knowledge_search "
    "first, even if the user doesn't name a specific topic. For a vague or broad request "
    "like a summary or 'what is this about', search for content-descriptive terms such as "
    "'abstract', 'introduction', or 'overview' -- these sections describe what the paper is "
    "about -- rather than meta-words like 'summary' or 'main findings', which won't match "
    "anything in the text itself.\n\n"
    "If the results you get back look like references, citations, a bibliography, "
    "acknowledgments, or otherwise don't actually describe the paper's content, that is a "
    "signal your query was wrong, not that the paper lacks a summary -- run another search "
    "with a different query (e.g. try 'abstract' if you first tried 'introduction', or a "
    "specific term from the paper's title/domain if you know it) before answering. Only "
    "give up on the documents after trying more than one query and still getting nothing "
    "useful.\n\n"
    "You also have web_search and web_fetch tools for information that isn't in the user's "
    "documents at all -- general/current information, or something the user explicitly asks "
    "you to look up online. Use web_search to find candidate pages, then web_fetch a specific "
    "URL to read its content before citing it. Don't use the web tools for questions clearly "
    "answerable from the project's documents; prefer knowledge_search for those."
)


@dataclass
class ChatResult:
    answer: str
    citations: list[dict] = field(default_factory=list)


def _default_llm() -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
        temperature=0.0,
    )


def build_graph(project_id: str, llm: BaseChatModel | None = None):
    knowledge_search = make_knowledge_search_tool(project_id)
    tools = [knowledge_search, *WEB_TOOLS]
    model = (llm or _default_llm()).bind_tools(tools)
    tool_node = ToolNode(tools)

    def agent_node(state: GraphState) -> dict:
        messages = state["messages"]
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]
        response = model.invoke(messages)
        return {"messages": [response]}

    def route_after_agent(state: GraphState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(GraphState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route_after_agent, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile()


def _citation_key(citation: dict) -> str | None:
    return citation.get("chunk_id") or citation.get("url")


def _citations_from_tool_result(tool_name: str, content: str) -> list[dict]:
    """Parses one tool's result content into zero or more citations. Shared by
    the sync path (_extract_citations, over full ToolMessages) and the
    streaming path (per on_tool_end event) so both agree on what counts as a
    citation -- see _extract_citations' docstring for the web_search rationale."""
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return []

    if tool_name == "knowledge_search":
        return [{"type": "document", **result} for result in payload.get("results", [])]

    if tool_name == "web_search":
        return [
            {"type": "web", "url": result["url"], "title": result.get("title")}
            for result in payload.get("results", [])
            if result.get("url")
        ]

    if tool_name == "web_fetch" and "error" not in payload and payload.get("url"):
        return [{"type": "web", "url": payload["url"], "title": payload.get("title")}]

    return []


def _extract_citations(messages: list) -> list[dict]:
    """Document citations come from knowledge_search hits. Web citations come
    from both web_search hits and web_fetch pages -- a model can (and often
    does) answer straight from a search snippet without a separate fetch, so
    treating only web_fetch as "used" would silently drop real citations."""
    citations: list[dict] = []
    seen_keys: set[str] = set()

    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        for citation in _citations_from_tool_result(message.name, message.content):
            key = _citation_key(citation)
            if key is None or key in seen_keys:
                continue
            seen_keys.add(key)
            citations.append(citation)

    return citations


class ChatSession:
    """Multi-turn wrapper (new-plan.md Phase 10): threads the full message
    history through the same compiled graph across turns, without needing a
    LangGraph checkpointer -- conversation state lives in this object only
    (not yet persisted to the app DB; that's new-plan.md section 27)."""

    def __init__(self, project_id: str, llm: BaseChatModel | None = None) -> None:
        self.project_id = project_id
        self._graph = build_graph(project_id, llm=llm)
        self._messages: list = []

    def ask(self, question: str) -> ChatResult:
        turn_start = len(self._messages)
        self._messages.append(HumanMessage(content=question))

        final_state = self._graph.invoke(
            {"messages": self._messages, "project_id": self.project_id}
        )
        self._messages = final_state["messages"]

        answer = self._messages[-1].content if self._messages else ""
        this_turn_messages = self._messages[turn_start:]
        return ChatResult(answer=answer, citations=_extract_citations(this_turn_messages))


def ask(project_id: str, question: str, llm: BaseChatModel | None = None) -> ChatResult:
    """Single-shot question, no conversation history kept afterward."""
    return ChatSession(project_id, llm=llm).ask(question)


async def astream_chat(project_id: str, question: str, llm: BaseChatModel | None = None):
    """Async generator of structured events (new-plan.md section 29):
    agent_started, tool_started/tool_finished, token, citation,
    agent_finished, error. Never exposes raw chain-of-thought -- only
    high-level activity, answer tokens, and citations."""
    compiled = build_graph(project_id, llm=llm)
    seen_keys: set[str] = set()
    answer_parts: list[str] = []
    last_ai_message_content = ""

    yield {"type": "agent_started"}

    try:
        async for event in compiled.astream_events(
            {"messages": [HumanMessage(content=question)], "project_id": project_id},
            version="v2",
        ):
            kind = event["event"]

            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                text = chunk.content if isinstance(chunk.content, str) else ""
                if text:
                    answer_parts.append(text)
                    yield {"type": "token", "text": text}

            elif kind == "on_chat_model_end":
                # Fallback for the final answer if the model doesn't support
                # true token streaming (on_chat_model_stream never fires) --
                # without this, agent_finished would report an empty answer
                # even though the model did answer.
                output = event["data"].get("output")
                content = getattr(output, "content", None)
                if isinstance(content, str) and content:
                    last_ai_message_content = content

            elif kind == "on_tool_start":
                yield {"type": "tool_started", "tool": event["name"]}

            elif kind == "on_tool_end":
                tool_name = event["name"]
                output = event["data"].get("output")
                content = getattr(output, "content", output)
                yield {"type": "tool_finished", "tool": tool_name}
                for citation in _citations_from_tool_result(tool_name, content):
                    key = _citation_key(citation)
                    if key is None or key in seen_keys:
                        continue
                    seen_keys.add(key)
                    # Nested, not spread: citation["type"] ("document"/"web")
                    # would otherwise silently clobber the event type below.
                    yield {"type": "citation", "citation": citation}
    except Exception as exc:  # noqa: BLE001 -- stream error boundary: surface as an event, not a crash
        yield {"type": "error", "message": str(exc)}
        return

    final_answer = "".join(answer_parts) or last_ai_message_content
    yield {"type": "agent_finished", "answer": final_answer}

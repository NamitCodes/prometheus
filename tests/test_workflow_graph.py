"""
Tests for the Phase 9 LangGraph workflow: the agent/tool loop and citation
extraction, driven by a scripted fake chat model (no live LLM call).
"""
from __future__ import annotations

import dataclasses

import pytest
import pytest_asyncio
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration
from langchain_core.outputs import ChatResult as LCChatResult
from pydantic import PrivateAttr
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import prometheus.db.session as db_session
import prometheus.retrieval.hybrid_search as hybrid_search_module
import prometheus.retrieval.vector_store as vector_store_module
import prometheus.services.projects as projects_service
from prometheus.db.base import Base
from prometheus.retrieval.ingestion import ingest_document
from prometheus.workflow.graph import ChatSession, ask, astream_chat


class ScriptedChatModel(BaseChatModel):
    """Returns each message in `responses` in order, ignoring the actual input --
    lets us script a tool-call round then a final-answer round deterministically."""

    responses: list[AIMessage]
    _index: int = PrivateAttr(default=0)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> LCChatResult:
        response = self.responses[self._index]
        self._index += 1
        return LCChatResult(generations=[ChatGeneration(message=response)])

    def bind_tools(self, tools, **kwargs):
        return self

    @property
    def _llm_type(self) -> str:
        return "scripted-fake"


def _isolate_stores(tmp_path, monkeypatch):
    isolated_settings = dataclasses.replace(
        vector_store_module.settings, chroma_persist_dir=str(tmp_path / "chroma")
    )
    monkeypatch.setattr(vector_store_module, "settings", isolated_settings)
    monkeypatch.setattr(hybrid_search_module, "settings", isolated_settings)
    monkeypatch.setattr(vector_store_module, "_vector_store", None)


def test_ask_calls_knowledge_search_and_returns_grounded_answer(tmp_path, monkeypatch):
    _isolate_stores(tmp_path, monkeypatch)

    doc = tmp_path / "notes.txt"
    doc.write_text("Retrieval-augmented generation reduces hallucination in LLM outputs.")
    ingest_document(str(doc), document_id="doc-1", metadata={"project_id": "project-1"})

    scripted = ScriptedChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "knowledge_search", "args": {"query": "hallucination"}, "id": "call-1"}
                ],
            ),
            AIMessage(content="RAG reduces hallucination [1]."),
        ]
    )

    result = ask("project-1", "Does RAG reduce hallucination?", llm=scripted)

    assert result.answer == "RAG reduces hallucination [1]."
    assert len(result.citations) == 1
    assert result.citations[0]["document_id"] == "doc-1"


def test_ask_answering_from_web_search_snippet_still_returns_citation(monkeypatch):
    """The model can answer directly from a search snippet without calling
    web_fetch -- that must still produce a citation, not silently drop it."""
    import prometheus.workflow.web_tools as web_tools_module

    class FakeSearchProvider:
        def search(self, query: str, max_results: int = 5) -> list[dict]:
            return [{"title": "RAG - Wikipedia", "url": "https://en.wikipedia.org/wiki/RAG", "snippet": "..."}]

    monkeypatch.setattr(web_tools_module, "get_web_search_provider", lambda: FakeSearchProvider())

    scripted = ScriptedChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "web_search", "args": {"query": "what is RAG"}, "id": "call-1"}
                ],
            ),
            AIMessage(content="RAG combines retrieval with generation [1]."),
        ]
    )

    result = ask("project-1", "What is RAG?", llm=scripted)

    assert result.answer == "RAG combines retrieval with generation [1]."
    assert result.citations == [
        {"type": "web", "url": "https://en.wikipedia.org/wiki/RAG", "title": "RAG - Wikipedia"}
    ]


def test_ask_calls_web_fetch_and_returns_web_citation(monkeypatch):
    import prometheus.workflow.web_tools as web_tools_module

    class FakeFetcher:
        def fetch(self, url: str) -> dict:
            return {"url": url, "title": "Example Page", "text": "some fetched content", "links": []}

    monkeypatch.setattr(web_tools_module, "get_web_fetcher", lambda: FakeFetcher())

    scripted = ScriptedChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "web_fetch",
                        "args": {"url": "https://example.com/"},
                        "id": "call-1",
                    }
                ],
            ),
            AIMessage(content="According to the page, some fetched content [1]."),
        ]
    )

    result = ask("project-1", "What does example.com say?", llm=scripted)

    assert result.answer == "According to the page, some fetched content [1]."
    assert result.citations == [
        {"type": "web", "url": "https://example.com/", "title": "Example Page"}
    ]


def test_ask_answers_directly_without_tool_call(tmp_path, monkeypatch):
    _isolate_stores(tmp_path, monkeypatch)

    scripted = ScriptedChatModel(responses=[AIMessage(content="I don't have enough information.")])

    result = ask("project-1", "What's the capital of Mars?", llm=scripted)

    assert result.answer == "I don't have enough information."
    assert result.citations == []


def test_chat_session_multi_turn_isolates_citations_per_turn(tmp_path, monkeypatch):
    _isolate_stores(tmp_path, monkeypatch)

    doc = tmp_path / "notes.txt"
    doc.write_text("Retrieval-augmented generation reduces hallucination in LLM outputs.")
    ingest_document(str(doc), document_id="doc-1", metadata={"project_id": "project-1"})

    scripted = ScriptedChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "knowledge_search", "args": {"query": "hallucination"}, "id": "call-1"}
                ],
            ),
            AIMessage(content="RAG reduces hallucination [1]."),
            AIMessage(content="It also improves factual grounding."),
        ]
    )

    session = ChatSession("project-1", llm=scripted)

    first = session.ask("Does RAG reduce hallucination?")
    assert first.answer == "RAG reduces hallucination [1]."
    assert len(first.citations) == 1

    second = session.ask("What else does it help with?")
    assert second.answer == "It also improves factual grounding."
    assert second.citations == [], "second turn made no new tool call, so it should carry no citations"

    # Full history (2 human turns + tool-call round-trip) persists across turns.
    assert len(session._messages) == 6


@pytest_asyncio.fixture
async def isolated_db(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test_app.db")
    session_local = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    monkeypatch.setattr(db_session, "engine", engine)
    monkeypatch.setattr(db_session, "AsyncSessionLocal", session_local)
    monkeypatch.setattr(projects_service, "AsyncSessionLocal", session_local)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield
    await engine.dispose()


@pytest.mark.asyncio
async def test_astream_chat_emits_expected_event_sequence(tmp_path, monkeypatch):
    """ScriptedChatModel only implements sync _generate (no true token
    streaming), so on_chat_model_stream never fires -- this also exercises
    the on_chat_model_end fallback that keeps agent_finished's answer from
    coming back empty in that case."""
    _isolate_stores(tmp_path, monkeypatch)

    doc = tmp_path / "notes.txt"
    doc.write_text("Retrieval-augmented generation reduces hallucination in LLM outputs.")
    ingest_document(str(doc), document_id="doc-1", metadata={"project_id": "project-1"})

    scripted = ScriptedChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "knowledge_search", "args": {"query": "hallucination"}, "id": "call-1"}
                ],
            ),
            AIMessage(content="RAG reduces hallucination [1]."),
        ]
    )

    events = [
        event async for event in astream_chat("project-1", "Does RAG reduce hallucination?", llm=scripted)
    ]
    event_types = [e["type"] for e in events]

    assert event_types == [
        "agent_started",
        "tool_started",
        "tool_finished",
        "citation",
        "agent_finished",
    ]

    citation_event = next(e for e in events if e["type"] == "citation")
    assert citation_event["citation"]["type"] == "document"
    assert citation_event["citation"]["document_id"] == "doc-1"

    final_event = events[-1]
    assert final_event["answer"] == "RAG reduces hallucination [1]."


def test_ask_rejects_unknown_project_via_cli(isolated_db):
    """Not the graph itself, but the CLI's project-existence guard --
    included here since it's the other half of Phase 9's acceptance test."""
    from typer.testing import CliRunner

    from prometheus.cli.main import app as cli_app

    runner = CliRunner()
    result = runner.invoke(cli_app, ["chat", "ask", "does-not-exist", "hello"])
    assert result.exit_code == 1

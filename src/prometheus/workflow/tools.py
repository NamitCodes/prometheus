"""LangGraph tools (new-plan.md section 20-22).

`project_id` is baked into the tool via closure at graph-build time, not
exposed as an LLM-fillable parameter -- the model must never be trusted to
supply its own scoping (new-plan.md section 21).
"""
from __future__ import annotations

import asyncio
import json

from langchain_core.tools import tool

from prometheus.services.retrieval import search_knowledge


def make_knowledge_search_tool(project_id: str):
    @tool
    def knowledge_search(query: str) -> str:
        """Search this project's ingested documents for passages relevant to the query."""
        chunks = asyncio.run(search_knowledge(query, project_id=project_id, limit=5))
        results = [
            {
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "page_number": c.page_number,
                "slide_number": c.slide_number,
                "text": c.text,
                "score": c.score,
            }
            for c in chunks
        ]
        return json.dumps({"results": results})

    return knowledge_search

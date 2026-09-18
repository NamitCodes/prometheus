"""Web LangGraph tools (new-plan.md section 22): web_search, web_fetch.

Unlike knowledge_search, these have no project-scoping concern -- they hit
the public internet, not the user's private documents -- so they're plain
tools rather than per-project factories.
"""
from __future__ import annotations

import json

from langchain_core.tools import tool

from prometheus.config import settings
from prometheus.providers.web import get_web_fetcher, get_web_search_provider
from prometheus.providers.web.security import UnsafeURLError


@tool
def web_search(query: str) -> str:
    """Search the public web for information not found in the project's documents."""
    results = get_web_search_provider().search(query, max_results=settings.web_search_max_results)
    return json.dumps({"results": results})


@tool
def web_fetch(url: str) -> str:
    """Fetch and extract the readable text content of a single web page URL."""
    try:
        page = get_web_fetcher().fetch(url)
    except UnsafeURLError as exc:
        return json.dumps({"error": str(exc)})
    except Exception as exc:  # noqa: BLE001 -- surface any fetch failure to the LLM as a tool result
        return json.dumps({"error": f"failed to fetch {url}: {exc}"})

    # Trim: full page text could be huge; the model doesn't need more than a
    # few thousand characters to answer from, and this keeps prompts bounded.
    truncated_text = page["text"][:8000]
    return json.dumps(
        {
            "url": page["url"],
            "title": page["title"],
            "text": truncated_text,
            "truncated": len(page["text"]) > len(truncated_text),
        }
    )


WEB_TOOLS = [web_search, web_fetch]

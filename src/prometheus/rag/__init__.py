"""
Grounded RAG generation layer for Prometheus.
"""
from prometheus.rag.context import build_context
from prometheus.rag.models import RagQueryRequest, RagResult, SourceRecord
from prometheus.rag.pipeline import INSUFFICIENT_CONTEXT_MESSAGE, query_rag
from prometheus.rag.prompts import RAG_SYSTEM_PROMPT, build_rag_user_prompt

__all__ = [
    "INSUFFICIENT_CONTEXT_MESSAGE",
    "RAG_SYSTEM_PROMPT",
    "RagQueryRequest",
    "RagResult",
    "SourceRecord",
    "build_context",
    "build_rag_user_prompt",
    "query_rag",
]

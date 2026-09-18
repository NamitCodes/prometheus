"""Celery background tasks (new-plan.md sections 6, 30-31).

Responsible for PDF/document processing, embedding generation, and other
long-running work -- kept separate from LangGraph, which owns the
conversational/reasoning workflow (see new-plan.md section 6).
"""

"""
Central configuration for Prometheus.

Loads settings from environment variables (see .env.example) and exposes
a single Settings object that every module should import from, instead of
calling os.environ directly. This keeps config swaps (e.g. Chroma -> Qdrant,
SQLite -> Postgres) to a single file.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    langsmith_project: str = os.getenv("LANGSMITH_PROJECT", "prometheus")
    langsmith_tracing: bool = os.getenv("LANGSMITH_TRACING", "true").lower() == "true"

    vector_db_backend: str = os.getenv("VECTOR_DB_BACKEND", "chroma")
    chroma_persist_dir: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")

    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./findings.db")

    semantic_scholar_api_key: str = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
    openalex_mailto: str = os.getenv("OPENALEX_MAILTO", "")

    mcp_server_port: int = int(os.getenv("MCP_SERVER_PORT", "8765"))

    # Per-role model / temperature overrides (Phase 3 tuning target).
    # TODO: move to a per-agent config dict once role tuning starts,
    # e.g. {"planner": {"model": "claude-...", "temperature": 0.7}, ...}


settings = Settings()

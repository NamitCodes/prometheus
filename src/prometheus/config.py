"""Central configuration for Prometheus.

Loads settings from environment variables (see .env.example) and exposes
a single Settings object that every module should import from, instead of
calling os.environ directly. This keeps config swaps (e.g. Chroma -> Qdrant,
SQLite -> Postgres) to a single file.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")

    langsmith_api_key: str = os.getenv("LANGSMITH_API_KEY", "")
    langsmith_project: str = os.getenv("LANGSMITH_PROJECT", "prometheus")
    langsmith_tracing: bool = os.getenv("LANGSMITH_TRACING", "true").lower() == "true"

    vector_db_backend: str = os.getenv("VECTOR_DB_BACKEND", "chroma")
    chroma_persist_dir: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key: str = os.getenv("QDRANT_API_KEY", "")

    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./findings.db")

    semantic_scholar_api_key: str = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
    openalex_mailto: str = os.getenv("OPENALEX_MAILTO", "")

    mcp_server_port: int = int(os.getenv("MCP_SERVER_PORT", "8765"))

    # Uppercase aliases for backward/cross compatibility
    @property
    def OPENROUTER_API_KEY(self) -> str:
        return self.openrouter_api_key

    @property
    def OPENROUTER_BASE_URL(self) -> str:
        return self.openrouter_base_url

    @property
    def OPENROUTER_MODEL(self) -> str:
        return self.openrouter_model

    @property
    def LANGSMITH_API_KEY(self) -> str:
        return self.langsmith_api_key

    @property
    def LANGSMITH_PROJECT(self) -> str:
        return self.langsmith_project

    @property
    def LANGSMITH_TRACING(self) -> bool:
        return self.langsmith_tracing

    @property
    def VECTOR_DB_BACKEND(self) -> str:
        return self.vector_db_backend

    @property
    def CHROMA_PERSIST_DIR(self) -> str:
        return self.chroma_persist_dir

    @property
    def QDRANT_URL(self) -> str:
        return self.qdrant_url

    @property
    def QDRANT_API_KEY(self) -> str:
        return self.qdrant_api_key

    @property
    def DATABASE_URL(self) -> str:
        return self.database_url

    @property
    def SEMANTIC_SCHOLAR_API_KEY(self) -> str:
        return self.semantic_scholar_api_key

    @property
    def OPENALEX_MAILTO(self) -> str:
        return self.openalex_mailto

    @property
    def MCP_SERVER_PORT(self) -> int:
        return self.mcp_server_port


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

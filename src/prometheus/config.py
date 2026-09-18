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

# LangChain/LangGraph read LANGCHAIN_TRACING_V2 / LANGSMITH_TRACING directly
# from the environment, independent of our Settings object below. Tracing
# with no API key just fails loudly on every LLM call (401s to LangSmith),
# so force it off here rather than relying on every .env to get this right.
if not os.getenv("LANGSMITH_API_KEY"):
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"


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

    # Application database: projects/documents/conversations (new-plan.md workspace
    # model). Deliberately separate from DATABASE_URL/findings.db, which holds the
    # older Prometheus reasoning-chain reports -- kept apart until that overlap
    # gets resolved.
    app_database_url: str = os.getenv("APP_DATABASE_URL", "sqlite+aiosqlite:///./data/app.db")

    # Local object storage for uploaded documents (new-plan.md section 33).
    document_storage_dir: str = os.getenv("DOCUMENT_STORAGE_DIR", "./data/documents")
    max_upload_size_mb: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))

    # Celery + Redis: background document processing (new-plan.md section 30).
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    # Runs Celery tasks synchronously in-process instead of via a worker+broker.
    # Tests flip this on directly; not meant to be set via env in normal use.
    celery_task_always_eager: bool = os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"

    semantic_scholar_api_key: str = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
    openalex_mailto: str = os.getenv("OPENALEX_MAILTO", "")

    # Web access (new-plan.md Phase 11). Provider is DuckDuckGo (via `ddgs`,
    # unofficial/scraped) for now -- swap for Brave Search once available,
    # see plan.md.
    web_search_max_results: int = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))
    web_fetch_timeout_seconds: float = float(os.getenv("WEB_FETCH_TIMEOUT_SECONDS", "10"))
    web_fetch_max_bytes: int = int(os.getenv("WEB_FETCH_MAX_BYTES", str(2 * 1024 * 1024)))
    web_crawl_max_pages: int = int(os.getenv("WEB_CRAWL_MAX_PAGES", "10"))
    web_crawl_max_depth: int = int(os.getenv("WEB_CRAWL_MAX_DEPTH", "2"))

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
    def APP_DATABASE_URL(self) -> str:
        return self.app_database_url

    @property
    def DOCUMENT_STORAGE_DIR(self) -> str:
        return self.document_storage_dir

    @property
    def MAX_UPLOAD_SIZE_MB(self) -> int:
        return self.max_upload_size_mb

    @property
    def REDIS_URL(self) -> str:
        return self.redis_url

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

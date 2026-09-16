"""Central configuration for Prometheus"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM (via OpenRouter, OpenAI-compatible API)
    OPENROUTER_API_KEY: str
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str

    # Observability
    LANGSMITH_API_KEY: str
    LANGSMITH_PROJECT: str = "prometheus"
    LANGSMITH_TRACING: bool = True


@dataclass(frozen=True)
class Settings:
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")

    # Relational store
    DATABASE_URL: str = "sqlite:///./findings.db"

    # External paper sources
    SEMANTIC_SCHOLAR_API_KEY: str
    OPENALEX_MAILTO: str

    # MCP server
    MCP_SERVER_PORT: int = 8765

    # Per-role model / temperature overrides (Phase 3 tuning target).
    # TODO: move to a per-agent config dict once role tuning starts,
    # e.g. {"planner": {"model": "claude-...", "temperature": 0.7}, ...}

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

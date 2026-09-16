"""
LLM abstraction layer for Prometheus.
"""
from prometheus.llm.base import BaseLLMClient, LLMConfigError, LLMError, LLMProviderError
from prometheus.llm.mock import MockLLMClient
from prometheus.llm.openrouter import OpenRouterClient
from prometheus.llm.service import generate_answer, get_llm_client

__all__ = [
    "BaseLLMClient",
    "LLMConfigError",
    "LLMError",
    "LLMProviderError",
    "MockLLMClient",
    "OpenRouterClient",
    "generate_answer",
    "get_llm_client",
]

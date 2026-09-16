"""
Base interfaces and domain exceptions for Prometheus LLM providers.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMError(Exception):
    """Base exception for all LLM service failures."""


class LLMProviderError(LLMError):
    """Raised when an external LLM API/provider fails or returns an HTTP/SDK error."""

    def __init__(self, message: str, provider: str = "OpenRouter", status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code


class LLMConfigError(LLMError):
    """Raised when LLM configuration (such as API keys or model names) is invalid."""


class BaseLLMClient(ABC):
    """Abstract interface for LLM text generation."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """Generate a text completion for the given prompt and optional system instruction.

        Parameters
        ----------
        prompt : str
            The user prompt or query context.
        system_prompt : str | None
            Optional system prompt specifying behavior and grounding rules.
        temperature : float
            Sampling temperature (0.0 for deterministic generation).
        max_tokens : int | None
            Max completion tokens.

        Returns
        -------
        str
            The generated text.
        """

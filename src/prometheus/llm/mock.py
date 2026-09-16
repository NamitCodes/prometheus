"""
Deterministic Mock LLM client for automated testing in Prometheus.
"""
from __future__ import annotations

from collections.abc import Callable

from prometheus.llm.base import BaseLLMClient


class MockLLMClient(BaseLLMClient):
    """Deterministic Mock LLM that returns pre-configured responses without making external API calls."""

    def __init__(
        self,
        default_response: str = "Mock answer generated from retrieved context [1].",
        custom_handler: Callable[[str, str | None], str] | None = None,
    ) -> None:
        self.default_response = default_response
        self.custom_handler = custom_handler
        self.call_history: list[dict] = []

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        self.call_history.append(
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self.custom_handler:
            return self.custom_handler(prompt, system_prompt)
        return self.default_response

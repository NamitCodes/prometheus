"""
OpenRouter LLM provider for Prometheus using OpenAI-compatible API.
"""
from __future__ import annotations

import logging
from typing import Any

from prometheus.config import settings
from prometheus.llm.base import BaseLLMClient, LLMConfigError, LLMProviderError

logger = logging.getLogger(__name__)


class OpenRouterClient(BaseLLMClient):
    """LLM client connecting to OpenRouter via OpenAI SDK interface."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        import os
        self.api_key = (api_key or os.getenv("OPENROUTER_API_KEY") or settings.openrouter_api_key).strip()
        self.base_url = (base_url or os.getenv("OPENROUTER_BASE_URL") or settings.openrouter_base_url).strip()
        self.model = (model or os.getenv("OPENROUTER_MODEL") or settings.openrouter_model).strip()
        self.timeout = timeout
        self._client: Any = None

    def _get_client(self) -> Any:
        if not self.api_key:
            raise LLMConfigError(
                "OPENROUTER_API_KEY is not set or empty. Provide an API key or configure test mock."
            )
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                default_headers={
                    "HTTP-Referer": "https://github.com/NamitCodes/prometheus",
                    "X-Title": "Prometheus Knowledge Platform",
                },
            )
        return self._client

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = 2048,
    ) -> str:
        client = self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens is not None and max_tokens > 0:
                kwargs["max_tokens"] = max_tokens

            response = client.chat.completions.create(**kwargs)

            if not response.choices:
                raise LLMProviderError("OpenRouter returned empty choices array.")

            content = response.choices[0].message.content
            return (content or "").strip()

        except LLMConfigError:
            raise
        except Exception as exc:
            logger.exception("OpenRouter generation failed")
            status_code = getattr(exc, "status_code", None)
            raise LLMProviderError(f"OpenRouter API error: {exc}", status_code=status_code) from exc

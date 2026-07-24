"""OpenAI-compatible client wrapper for LM Studio."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.config import AppConfig


class LlmClientError(RuntimeError):
    """Raised when LLM request fails or response is unusable."""


@dataclass(frozen=True)
class LlmResponse:
    text: str
    raw_response: Any


class LlmClient:
    def __init__(
        self,
        base_url: str,
        model_name: str,
        timeout: float = 60.0,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.base_url = base_url
        self.model_name = model_name
        self.timeout = timeout
        self._client_factory = client_factory or _default_client_factory
        self._client = self._client_factory(base_url=self.base_url, timeout=self.timeout)

    @classmethod
    def from_config(
        cls,
        config: AppConfig,
        timeout: float = 60.0,
        client_factory: Callable[..., Any] | None = None,
    ) -> "LlmClient":
        return cls(
            base_url=config.lmstudio_base_url,
            model_name=config.model_name,
            timeout=timeout,
            client_factory=client_factory,
        )

    def prompt(self, prompt_text: str, system_prompt: str | None = None) -> LlmResponse:
        if not prompt_text.strip():
            raise LlmClientError("Prompt text must not be empty")

        messages: list[dict[str, str]] = []
        if system_prompt and system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt.strip()})
        messages.append({"role": "user", "content": prompt_text.strip()})

        try:
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=messages,
            )
        except Exception as error:  # noqa: BLE001
            raise LlmClientError(f"LLM request failed: {error}") from error

        text = _extract_text(response)
        if not text:
            raise LlmClientError("LLM response did not contain message content")

        return LlmResponse(text=text, raw_response=response)


def _extract_text(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if not choices:
        return ""

    message = getattr(choices[0], "message", None)
    if message is None:
        return ""

    content = getattr(message, "content", None)
    if not isinstance(content, str):
        return ""

    return content.strip()


def _default_client_factory(*, base_url: str, timeout: float) -> Any:
    from openai import OpenAI

    return OpenAI(base_url=base_url, timeout=timeout)

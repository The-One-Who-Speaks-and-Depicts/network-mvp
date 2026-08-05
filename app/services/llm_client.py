"""OpenAI-compatible client wrapper for LM Studio."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Callable, Protocol

from openai import OpenAI

from app.config import AppConfig


class LlmClientError(RuntimeError):
    """Operational provider/request/response failure, not invalid caller input."""


class PromptingClient(Protocol):
    """Minimal interface required by pipeline stages and their test doubles."""

    def prompt(self, prompt_text: str, system_prompt: str | None = None) -> "LlmResponse":
        """Return a response for a prompt; pipeline clients and test doubles implement this."""

        # Protocol stubs use an ellipsis to provide a signature without runtime behavior.
        # pylint: disable=unnecessary-ellipsis
        ...


@dataclass(frozen=True)
class LlmResponse:
    """Normalized response text plus the provider-native response object."""

    text: str
    raw_response: Any


class LlmClient:
    """Adapter around an OpenAI-compatible chat-completions endpoint."""

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
        """Send one prompt and raise ``LlmClientError`` for unusable responses."""

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
            raise LlmClientError(
                "LLM request failed. "
                f"base_url={self.base_url} model={self.model_name} "
                f"details={_format_exception_chain(error)}"
            ) from error

        text = _extract_text(response)
        if not text:
            raise LlmClientError("LLM response did not contain message content")

        return LlmResponse(text=text, raw_response=response)


def _format_exception_chain(error: BaseException) -> str:
    chain: list[str] = []
    current: BaseException | None = error
    while current is not None:
        chain.append(f"{type(current).__name__}({current!r})")
        next_error = current.__cause__ or current.__context__
        if next_error is current:
            break
        current = next_error
    return " <- ".join(chain)


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
    api_key = os.environ.get("OPENAI_API_KEY", "lm-studio")
    return OpenAI(
        base_url=base_url,
        timeout=timeout,
        api_key=api_key,
    )

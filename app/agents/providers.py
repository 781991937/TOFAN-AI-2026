"""Provider-neutral AI contracts and a live OpenAI Responses adapter.

The rest of TOFAN depends on this contract instead of a vendor SDK.
Secrets are read from environment variables and are never stored in source.
"""

from dataclasses import dataclass
import os
from typing import Protocol

from openai import OpenAI


class AgentProviderError(RuntimeError):
    """Raised when an AI provider cannot complete a request."""


@dataclass(frozen=True)
class AgentMessage:
    role: str
    content: str


@dataclass(frozen=True)
class AgentResponse:
    content: str
    provider: str
    model: str


class AIProvider(Protocol):
    provider_name: str
    model_name: str

    def generate(
        self,
        messages: list[AgentMessage],
        *,
        system_prompt: str | None = None,
    ) -> AgentResponse:
        """Generate one model response."""


class OpenAIResponsesProvider:
    """OpenAI Responses API adapter configured by environment variables."""

    provider_name = "openai"

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self._api_key:
            raise AgentProviderError("OPENAI_API_KEY is not configured.")
        self.model_name = model or os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
        self._client = OpenAI(api_key=self._api_key)

    def generate(
        self,
        messages: list[AgentMessage],
        *,
        system_prompt: str | None = None,
    ) -> AgentResponse:
        try:
            input_messages: list[dict[str, str]] = []
            if system_prompt:
                input_messages.append({"role": "system", "content": system_prompt})
            input_messages.extend(
                {"role": message.role, "content": message.content}
                for message in messages
            )
            response = self._client.responses.create(
                model=self.model_name,
                input=input_messages,
            )
        except Exception as exc:
            raise AgentProviderError(f"OpenAI request failed: {exc}") from exc

        return AgentResponse(
            content=response.output_text,
            provider=self.provider_name,
            model=self.model_name,
        )

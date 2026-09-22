"""Provider-neutral AI contracts and OpenAI Responses tool calling."""

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
    tool_calls: tuple[dict, ...] = ()


class AIProvider(Protocol):
    provider_name: str
    model_name: str

    def generate(
        self,
        messages: list[AgentMessage],
        *,
        system_prompt: str | None = None,
        tools: list[dict] | None = None,
    ) -> AgentResponse:
        ...


class OpenAIResponsesProvider:
    provider_name = "openai"

    def __init__(self, *, api_key: str | None = None, model: str | None = None, provider: str = "openai") -> None:
        selected_provider = (provider or "openai").strip().lower()
        if selected_provider != "openai":
            raise AgentProviderError(f"Unsupported AI provider: {selected_provider}")
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
        tools: list[dict] | None = None,
    ) -> AgentResponse:
        try:
            input_messages: list[dict[str, str]] = []
            if system_prompt:
                input_messages.append({"role": "system", "content": system_prompt})
            input_messages.extend({"role": m.role, "content": m.content} for m in messages)

            response = self._client.responses.create(
                model=self.model_name,
                input=input_messages,
                tools=tools or None,
            )

            calls = []
            for item in response.output:
                if getattr(item, "type", None) == "function_call":
                    calls.append(
                        {
                            "call_id": item.call_id,
                            "name": item.name,
                            "arguments": item.arguments,
                        }
                    )

            return AgentResponse(
                content=response.output_text or "",
                provider=self.provider_name,
                model=self.model_name,
                tool_calls=tuple(calls),
            )
        except Exception as exc:
            raise AgentProviderError(f"OpenAI request failed: {exc}") from exc

    def submit_tool_outputs(
        self,
        *,
        messages: list[dict],
        tool_outputs: list[dict],
        system_prompt: str | None = None,
        tools: list[dict] | None = None,
    ) -> AgentResponse:
        try:
            input_messages: list = []
            if system_prompt:
                input_messages.append({"role": "system", "content": system_prompt})
            input_messages.extend(messages)
            input_messages.extend(
                {
                    "type": "function_call_output",
                    "call_id": item["call_id"],
                    "output": item["output"],
                }
                for item in tool_outputs
            )
            response = self._client.responses.create(
                model=self.model_name,
                input=input_messages,
                tools=tools or [],
            )
            calls = []
            for item in response.output:
                if getattr(item, "type", None) == "function_call":
                    calls.append({
                        "call_id": item.call_id,
                        "name": item.name,
                        "arguments": item.arguments,
                    })
            return AgentResponse(
                content=response.output_text or "",
                provider=self.provider_name,
                model=self.model_name,
                tool_calls=tuple(calls),
            )
        except Exception as exc:
            raise AgentProviderError(f"OpenAI tool-output request failed: {exc}") from exc

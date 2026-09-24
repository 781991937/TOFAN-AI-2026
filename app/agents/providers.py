"""Provider-neutral AI contracts with OpenAI and Gemini-compatible runtimes."""

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
    """Unified provider adapter.

    openai uses the native Responses API. gemini uses Google's
    OpenAI-compatible Chat Completions endpoint.
    """

    def __init__(self, *, api_key: str | None = None, model: str | None = None, provider: str = "openai") -> None:
        selected_provider = (provider or "openai").strip().lower()
        if selected_provider not in {"openai", "gemini"}:
            raise AgentProviderError(f"Unsupported AI provider: {selected_provider}")

        if selected_provider == "gemini":
            self._api_key = api_key or os.getenv("GEMINI_API_KEY")
            self.model_name = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            if not self._api_key:
                raise AgentProviderError("GEMINI_API_KEY is not configured.")
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=os.getenv(
                    "GEMINI_OPENAI_BASE_URL",
                    "https://generativelanguage.googleapis.com/v1beta/openai/",
                ),
            )
        else:
            self._api_key = api_key or os.getenv("OPENAI_API_KEY")
            self.model_name = model or os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
            if not self._api_key:
                raise AgentProviderError("OPENAI_API_KEY is not configured.")
            self._client = OpenAI(api_key=self._api_key)

        self.provider_name = selected_provider

    @staticmethod
    def _chat_tools(tools: list[dict] | None) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters") or {"type": "object", "properties": {}},
                },
            }
            for tool in (tools or [])
            if tool.get("type") == "function"
        ]

    def _chat_response(self, message) -> AgentResponse:
        calls = tuple(
            {
                "call_id": item.id,
                "name": item.function.name,
                "arguments": item.function.arguments or "{}",
            }
            for item in (getattr(message, "tool_calls", None) or [])
        )
        return AgentResponse(
            content=getattr(message, "content", None) or "",
            provider=self.provider_name,
            model=self.model_name,
            tool_calls=calls,
        )

    def generate(self, messages: list[AgentMessage], *, system_prompt: str | None = None, tools: list[dict] | None = None) -> AgentResponse:
        if self.provider_name == "gemini":
            try:
                input_messages: list[dict] = []
                if system_prompt:
                    input_messages.append({"role": "system", "content": system_prompt})
                input_messages.extend({"role": m.role, "content": m.content} for m in messages)
                return self._chat_response(
                    self._client.chat.completions.create(
                        model=self.model_name,
                        messages=input_messages,
                        tools=self._chat_tools(tools),
                    ).choices[0].message
                )
            except Exception as exc:
                raise AgentProviderError(f"Gemini request failed: {exc}") from exc

        try:
            input_messages: list[dict[str, str]] = []
            if system_prompt:
                input_messages.append({"role": "system", "content": system_prompt})
            input_messages.extend({"role": m.role, "content": m.content} for m in messages)
            response = self._client.responses.create(model=self.model_name, input=input_messages, tools=tools or None)
            calls = tuple(
                {"call_id": item.call_id, "name": item.name, "arguments": item.arguments}
                for item in response.output
                if getattr(item, "type", None) == "function_call"
            )
            return AgentResponse(response.output_text or "", self.provider_name, self.model_name, calls)
        except Exception as exc:
            raise AgentProviderError(f"OpenAI request failed: {exc}") from exc

    def submit_tool_outputs(self, *, messages: list[dict], tool_outputs: list[dict], system_prompt: str | None = None, tools: list[dict] | None = None) -> AgentResponse:
        if self.provider_name == "gemini":
            try:
                chat_messages: list[dict] = []
                if system_prompt:
                    chat_messages.append({"role": "system", "content": system_prompt})
                for item in messages:
                    if item.get("type") == "function_call":
                        chat_messages.append({
                            "role": "assistant",
                            "tool_calls": [{
                                "id": item["call_id"],
                                "type": "function",
                                "function": {"name": item["name"], "arguments": item.get("arguments", "{}")},
                            }],
                        })
                    elif item.get("role") in {"user", "assistant"}:
                        chat_messages.append({"role": item["role"], "content": item.get("content", "")})
                for item in tool_outputs:
                    chat_messages.append({
                        "role": "tool",
                        "tool_call_id": item["call_id"],
                        "content": item["output"],
                    })
                return self._chat_response(
                    self._client.chat.completions.create(
                        model=self.model_name,
                        messages=chat_messages,
                        tools=self._chat_tools(tools),
                    ).choices[0].message
                )
            except Exception as exc:
                raise AgentProviderError(f"Gemini tool-output request failed: {exc}") from exc

        try:
            input_messages: list = []
            if system_prompt:
                input_messages.append({"role": "system", "content": system_prompt})
            input_messages.extend(messages)
            input_messages.extend({"type": "function_call_output", "call_id": item["call_id"], "output": item["output"]} for item in tool_outputs)
            response = self._client.responses.create(model=self.model_name, input=input_messages, tools=tools or [])
            calls = tuple(
                {"call_id": item.call_id, "name": item.name, "arguments": item.arguments}
                for item in response.output
                if getattr(item, "type", None) == "function_call"
            )
            return AgentResponse(response.output_text or "", self.provider_name, self.model_name, calls)
        except Exception as exc:
            raise AgentProviderError(f"OpenAI tool-output request failed: {exc}") from exc

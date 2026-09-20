"""Provider-neutral contracts for TOFAN's future AI model integrations.

The academy depends on these contracts rather than a specific vendor SDK.
Actual OpenAI/Gemini adapters can be added later without changing agent tools.
"""

from dataclasses import dataclass
from typing import Protocol


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
